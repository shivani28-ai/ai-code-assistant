# AI Code Assistant

A full-stack developer tool that takes a GitHub repository URL, explains the codebase in plain English, and answers natural-language questions about it using Retrieval-Augmented Generation (RAG).

## Features

- **Repo analysis**: paste a GitHub link and get a project summary, tech stack, main components and how it works
- **Ask My Codebase**: ask questions like "Where is authentication handled?" and get answers grounded in the repo's files, with the relevant file paths shown
- **Semantic search**: code is embedded and stored in a vector database, so questions are matched by meaning, not just keywords

## How it works

1. The React frontend sends a GitHub URL to the FastAPI backend
2. The backend clones the repo with GitPython and reads its files
3. File contents are embedded with sentence-transformers (all-MiniLM-L6-v2) and stored in ChromaDB
4. For a summary, a sample of the code is sent to GPT-OSS 120B through the Groq API
5. For a question, the most relevant files are retrieved from ChromaDB and passed to the LLM as context

## Tech stack

- **Backend:** Python, FastAPI, Uvicorn, GitPython
- **AI / RAG:** Groq API (openai/gpt-oss-120b), sentence-transformers, ChromaDB
- **Frontend:** React

## Run it locally

You need Python 3, Node.js and a free Groq API key from console.groq.com.

Backend:

    git clone https://github.com/shivani28-ai/ai-code-assistant.git
    cd ai-code-assistant
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    echo "GROQ_API_KEY=your-key-here" > .env
    uvicorn main:app --reload

Frontend (in a second terminal):

    cd ai-code-assistant/frontend
    npm install
    npm start

Then open http://localhost:3000 and paste a public GitHub repo URL.

## Limitations

- Only the first ~1000 characters of each file are embedded, so very large files are partially indexed
- The vector store is in memory and resets when the server restarts
- Works with public repositories only

## Author

Shivani
