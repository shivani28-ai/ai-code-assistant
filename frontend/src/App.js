import { useState } from "react";
import "./App.css";

function App() {
  const [githubUrl, setGithubUrl] = useState("");
  const [loading, setLoading] = useState(false);
  const [analysis, setAnalysis] = useState(null);
  const [repoId, setRepoId] = useState("");

  const [question, setQuestion] = useState("");
  const [askLoading, setAskLoading] = useState(false);
  const [chatHistory, setChatHistory] = useState([]);

  const handleAnalyze = async () => {
    setLoading(true);
    setAnalysis(null);
    try {
      const res = await fetch("http://127.0.0.1:8000/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ github_url: githubUrl }),
      });
      const data = await res.json();
      setAnalysis(data);
      setRepoId(data.repo_id);
    } catch (err) {
      alert("Error analyzing repo: " + err.message);
    }
    setLoading(false);
  };

  const handleAsk = async () => {
    if (!question.trim()) return;
    setAskLoading(true);
    const currentQuestion = question;
    setQuestion("");

    try {
      const res = await fetch("http://127.0.0.1:8000/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: currentQuestion, repo_id: repoId }),
      });
      const data = await res.json();
      setChatHistory((prev) => [
        ...prev,
        { question: currentQuestion, answer: data.answer, files: data.relevant_files },
      ]);
    } catch (err) {
      alert("Error asking question: " + err.message);
    }
    setAskLoading(false);
  };

  return (
    <div className="App">
      <h1>AI Code Assistant</h1>
      <p className="subtitle">Paste a GitHub repo link and let AI explain the codebase</p>

      <div className="input-row">
        <input
          type="text"
          placeholder="https://github.com/owner/repo"
          value={githubUrl}
          onChange={(e) => setGithubUrl(e.target.value)}
        />
        <button onClick={handleAnalyze} disabled={loading || !githubUrl}>
          {loading ? "Analyzing..." : "Analyze Repo"}
        </button>
      </div>

      {loading && <p className="status">Cloning repo and running AI analysis... this can take 20-30 seconds.</p>}

      {analysis && (
        <div className="analysis-box">
          <h2>Analysis</h2>
          <p><strong>Repo:</strong> {analysis.repo}</p>
          <p><strong>Total files:</strong> {analysis.total_files}</p>
          <pre>{analysis.ai_analysis}</pre>
        </div>
      )}

      {repoId && (
        <div className="chat-section">
          <h2>Ask My Codebase</h2>

          <div className="chat-history">
            {chatHistory.map((item, idx) => (
              <div key={idx} className="chat-item">
                <p className="chat-question">🧑 {item.question}</p>
                <p className="chat-answer">🤖 {item.answer}</p>
                <p className="chat-files">Files: {item.files.join(", ")}</p>
              </div>
            ))}
          </div>

          <div className="input-row">
            <input
              type="text"
              placeholder="Ask something about this codebase..."
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleAsk()}
            />
            <button onClick={handleAsk} disabled={askLoading || !question}>
              {askLoading ? "Thinking..." : "Ask"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

export default App;
