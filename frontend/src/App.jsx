import React, { startTransition, useEffect, useRef, useState } from "react";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";
const CONFIGURED_API_PREFIX = import.meta.env.VITE_API_ROUTE_PREFIX;
const API_PREFIX_CANDIDATES = [
  CONFIGURED_API_PREFIX,
  "/api",
  "/api/ticketing",
].filter((value, index, values) => value && values.indexOf(value) === index);

function App() {
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState([
    {
      id: "welcome",
      role: "assistant",
      content: "Ask Any Question About Your ERP Data",
      status: "ready",
      meta: "",
    },
  ]);
  const [isRunning, setIsRunning] = useState(false);
  const [runId, setRunId] = useState("");
  const [statusText, setStatusText] = useState("Ready");
  const eventSourceRef = useRef(null);
  const listRef = useRef(null);
  const lastSqlRef = useRef("");
  const lastErrorRef = useRef("");
  const apiPrefixRef = useRef(API_PREFIX_CANDIDATES[0] ?? "/api");

  useEffect(() => {
    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }
    };
  }, []);

  useEffect(() => {
    const container = listRef.current;
    if (!container) {
      return;
    }
    container.scrollTop = container.scrollHeight;
  }, [messages]);

  function updateAssistantMessage(messageId, updater) {
    startTransition(() => {
      setMessages((current) =>
        current.map((message) =>
          message.id === messageId ? { ...message, ...updater(message) } : message,
        ),
      );
    });
  }

  async function handleSubmit(event) {
    event.preventDefault();
    const trimmedQuestion = question.trim();
    if (!trimmedQuestion || isRunning) {
      return;
    }

    const userMessageId = `user-${Date.now()}`;
    const assistantMessageId = `assistant-${Date.now()}`;

    setMessages((current) => [
      ...current,
      { id: userMessageId, role: "user", content: trimmedQuestion, status: "sent", meta: "" },
      {
        id: assistantMessageId,
        role: "assistant",
        content: "",
        status: "thinking",
        meta: "Thinking...",
      },
    ]);
    setQuestion("");
    setIsRunning(true);
    setStatusText("Starting");

    try {
      let payload = null;
      let lastErrorText = "";

      for (const prefix of API_PREFIX_CANDIDATES) {
        const response = await fetch(`${API_BASE_URL}${prefix}/runs`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ question: trimmedQuestion }),
        });

        if (response.ok) {
          payload = await response.json();
          apiPrefixRef.current = prefix;
          break;
        }

        lastErrorText = await response.text();
        if (response.status !== 404) {
          throw new Error(lastErrorText || "Failed to start workflow run.");
        }
      }

      if (!payload) {
        throw new Error(lastErrorText || "Failed to start workflow run.");
      }

      setRunId(payload.run_id);
      subscribeToRun(payload.run_id, assistantMessageId);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Unexpected error";
      updateAssistantMessage(assistantMessageId, () => ({
        content: message,
        status: "error",
        meta: "Request failed",
      }));
      setStatusText("Failed");
      setIsRunning(false);
    }
  }

  function subscribeToRun(nextRunId, assistantMessageId) {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }

    const source = new EventSource(
      `${API_BASE_URL}${apiPrefixRef.current}/runs/${nextRunId}/events`,
    );
    eventSourceRef.current = source;
    lastSqlRef.current = "";
    lastErrorRef.current = "";

    const applySnapshot = (snapshot) => {
      if (!snapshot) {
        return;
      }

      const currentNode = snapshot.current_node || "Working";
      const executionStatus = snapshot.execution_status || "running";
      const finalAnswer = snapshot.final_answer;
      const errors = snapshot.errors ?? [];
      const generatedSql = snapshot.generated_sql ?? "";

      setStatusText(currentNode);

      if (generatedSql && generatedSql !== lastSqlRef.current) {
        console.log("[ERP AI Agent] Generated SQL\n", generatedSql);
        lastSqlRef.current = generatedSql;
      }

      if (errors.length > 0) {
        const nextErrorText = errors.join(" | ");
        if (nextErrorText !== lastErrorRef.current) {
          console.error("[ERP AI Agent] Workflow Errors\n", nextErrorText);
          lastErrorRef.current = nextErrorText;
        }
      }

      if (finalAnswer) {
        updateAssistantMessage(assistantMessageId, () => ({
          content: finalAnswer,
          status: errors.length > 0 ? "warning" : "done",
          meta: currentNode,
        }));
        return;
      }

      if (errors.length > 0 && executionStatus === "failed") {
        updateAssistantMessage(assistantMessageId, () => ({
          content: errors.join(" "),
          status: "error",
          meta: currentNode,
        }));
        return;
      }

      updateAssistantMessage(assistantMessageId, () => ({
        content: "",
        status: "thinking",
        meta: currentNode,
      }));
    };

    const handleEvent = (event) => {
      const data = JSON.parse(event.data);
      applySnapshot(data.snapshot);
    };

    source.addEventListener("workflow_started", handleEvent);
    source.addEventListener("trace_updated", handleEvent);
    source.addEventListener("node_trace", handleEvent);
    source.addEventListener("stream_state", handleEvent);
    source.addEventListener("raw_event", handleEvent);

    source.addEventListener("workflow_completed", (event) => {
      const data = JSON.parse(event.data);
      applySnapshot(data.snapshot);

      if (data.status === "failed") {
        updateAssistantMessage(assistantMessageId, (message) => ({
          content: message.content || "Workflow failed.",
          status: "error",
          meta: "Failed",
        }));
        setStatusText("Failed");
      } else {
        updateAssistantMessage(assistantMessageId, (message) => ({
          content: message.content || "No answer was returned.",
          status: "done",
          meta: "Completed",
        }));
        setStatusText("Completed");
      }

      setIsRunning(false);
      source.close();
    });

    source.addEventListener("error", (event) => {
      let message = "Workflow error";
      try {
        const data = JSON.parse(event.data);
        message = data.message ?? message;
      } catch {
        // Keep generic fallback.
      }
      updateAssistantMessage(assistantMessageId, () => ({
        content: message,
        status: "error",
        meta: "Failed",
      }));
      setStatusText("Failed");
      setIsRunning(false);
    });

    source.onerror = () => {
      if (source.readyState === EventSource.CLOSED) {
        return;
      }
      updateAssistantMessage(assistantMessageId, (message) => ({
        content: message.content || "Connection to the backend was interrupted.",
        status: message.content ? message.status : "error",
        meta: "Disconnected",
      }));
      setStatusText("Disconnected");
      setIsRunning(false);
    };
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div>
          <p className="brand-eyebrow">ERP AI Agent</p>
          <h1>Chat</h1>
          <p className="brand-copy">Ask a question and get only the final backend answer.</p>
        </div>
        <div className="status-card">
          <span className="status-label">Status</span>
          <strong>{statusText}</strong>
          <p>{runId ? `Run ID: ${runId}` : "No active run"}</p>
        </div>
      </aside>

      <main className="chat-shell">
        <div className="message-list" ref={listRef}>
          {messages.map((message) => (
            <article className={`message-row ${message.role}`} key={message.id}>
              <div className="avatar">{message.role === "user" ? "U" : "AI"}</div>
              <div className={`bubble ${message.role} ${message.status}`}>
                <div className="bubble-header">
                  <span>{message.role === "user" ? "You" : "Assistant"}</span>
                  {message.meta ? <small>{message.meta}</small> : null}
                </div>
                {message.status === "thinking" && !message.content ? (
                  <div className="typing-indicator">
                    <span />
                    <span />
                    <span />
                  </div>
                ) : (
                  <p>{message.content}</p>
                )}
              </div>
            </article>
          ))}
        </div>

        <form className="composer-shell" onSubmit={handleSubmit}>
          <textarea
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            className="composer"
            placeholder="Ask about invoices, suppliers, payments, or ERP data..."
            rows={1}
          />
          <button className="send-button" type="submit" disabled={isRunning || !question.trim()}>
            {isRunning ? "Running..." : "Send"}
          </button>
        </form>
      </main>
    </div>
  );
}

export default App;
