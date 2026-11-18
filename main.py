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
        code_summary = ""

        repo_id = request.github_url.split("/")[-1]
        collection = chroma_client.get_or_create_collection(name=repo_id)

        for root_dir, dirs, files in os.walk(tmp_dir):
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            for filename in files:
                full_path = os.path.join(root_dir, filename)
                relative_path = os.path.relpath(full_path, tmp_dir)

                try:
                    with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read(3000)
                except Exception:
                    content = "[could not read file]"

                files_data.append({
                    "path": relative_path,
                    "content": content
                })

                code_summary += f"\n\n--- {relative_path} ---\n{content[:500]}"

                if content != "[could not read file]" and len(content.strip()) > 0:
                    embedding = embedding_model.encode(content[:1000]).tolist()
                    collection.add(
                        documents=[content[:1000]],
                        embeddings=[embedding],
                        ids=[relative_path],
                        metadatas=[{"path": relative_path}]
                    )

        response = client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert software engineer. Analyze the given codebase and provide: 1) Project summary 2) Tech stack 3) Main components 4) How it works"
                },
                {
                    "role": "user",
                    "content": f"Analyze this codebase:\n{code_summary[:8000]}"
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
            n_results=3
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
                    "content": "You are an expert software engineer. Answer questions about the codebase using the provided code context."
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
            "relevant_files": [m["path"] for m in results["metadatas"][0]]
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")