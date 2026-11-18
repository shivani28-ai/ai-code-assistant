import os
import shutil
import tempfile
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import git
from groq import Groq
from dotenv import load_dotenv
import chromadb
from sentence_transformers import SentenceTransformer

load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

client = Groq(api_key=os.getenv("GROQ_API_KEY"))
embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
chroma_client = chromadb.Client()

SKIP_EXT = (".png", ".jpg", ".jpeg", ".gif", ".ico", ".svg", ".lock", ".map", ".woff", ".woff2", ".pdf", ".mp4", ".zip")
SKIP_NAMES = ("package-lock.json", "yarn.lock", "pnpm-lock.yaml", "poetry.lock", ".gitignore")
KEY_NAMES = ("readme.md", "main.py", "app.py", "server.py", "index.js", "app.js", "package.json", "pyproject.toml")


def is_noise(path):
    name = os.path.basename(path).lower()
    return name in SKIP_NAMES or name.endswith(SKIP_EXT)


def file_priority(path):
    return 0 if os.path.basename(path).lower() in KEY_NAMES else 1


def build_summary(parts, limit=12000):
    parts.sort(key=lambda p: p[0])
    return "".join(text for _, text in parts)[:limit]


@app.get("/")
def root():
    return {"message": "AI Code Assistant is running"}


class RepoRequest(BaseModel):
    github_url: str


class QuestionRequest(BaseModel):
    question: str
    repo_id: str


@app.post("/analyze")
def analyze_repo(request: RepoRequest):
    tmp_dir = tempfile.mkdtemp()
    try:
        git.Repo.clone_from(request.github_url, tmp_dir)

        files_data = []
        summary_parts = []

        repo_id = request.github_url.split("/")[-1]
        try:
            chroma_client.delete_collection(name=repo_id)
        except Exception:
            pass
        collection = chroma_client.get_or_create_collection(name=repo_id)

        for root_dir, dirs, files in os.walk(tmp_dir):
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            for filename in files:
                full_path = os.path.join(root_dir, filename)
                relative_path = os.path.relpath(full_path, tmp_dir)

                try:
                    with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read(20000)
                except Exception:
                    content = "[could not read file]"

                files_data.append({
                    "path": relative_path,
                    "content": content
                })

                if not is_noise(relative_path):
                    cap = 6000 if file_priority(relative_path) == 0 else 600
                    summary_parts.append((file_priority(relative_path), f"\n\n--- {relative_path} ---\n{content[:cap]}"))

                if content != "[could not read file]" and content.strip() and not is_noise(relative_path):
                    chunks = [content[i:i + 1000] for i in range(0, len(content), 1000)]
                    chunks = [c for c in chunks if c.strip()]
                    if chunks:
                        collection.add(
                            documents=chunks,
                            embeddings=embedding_model.encode(chunks).tolist(),
                            ids=[f"{relative_path}#{n}" for n in range(len(chunks))],
                            metadatas=[{"path": relative_path}] * len(chunks)
                        )

        response = client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert software engineer. Analyze the given codebase using ONLY the provided files. Never invent libraries, files or features that are not shown; if something is not visible, say it is not shown. Provide: 1) Project summary 2) Tech stack 3) Main components 4) How it works"
                },
                {
                    "role": "user",
                    "content": f"Analyze this codebase:\n{build_summary(summary_parts)}"
                }
            ]
        )

        ai_analysis = response.choices[0].message.content

        return {
            "repo": request.github_url,
            "repo_id": repo_id,
            "total_files": len(files_data),
            "ai_analysis": ai_analysis,
        }

    except git.exc.GitCommandError as e:
        raise HTTPException(status_code=400, detail=f"Git clone failed: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


@app.post("/ask")
def ask_question(request: QuestionRequest):
    try:
        collection = chroma_client.get_collection(name=request.repo_id)

        question_embedding = embedding_model.encode(request.question).tolist()
        results = collection.query(
            query_embeddings=[question_embedding],
            n_results=5
        )

        context = ""
        for i, doc in enumerate(results["documents"][0]):
            path = results["metadatas"][0][i]["path"]
            context += f"\n\n--- {path} ---\n{doc}"

        response = client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert software engineer. Answer questions about the codebase using ONLY the provided code context. Never invent functions, files, line numbers or libraries. If the context does not contain the answer, say you could not find it in the retrieved files."
                },
                {
                    "role": "user",
                    "content": f"Code context:\n{context}\n\nQuestion: {request.question}"
                }
            ]
        )

        return {
            "question": request.question,
            "answer": response.choices[0].message.content,
            "relevant_files": list(dict.fromkeys(m["path"] for m in results["metadatas"][0]))
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")