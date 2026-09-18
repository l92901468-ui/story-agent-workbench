const runBtn = document.getElementById("runBtn");
const questionInput = document.getElementById("question");
const statusEl = document.getElementById("status");
const retrievalEl = document.getElementById("retrieval");
const draftsEl = document.getElementById("drafts");
const chatEl = document.getElementById("chat");
const finalPlanEl = document.getElementById("finalPlan");

function setStatus(text) {
  statusEl.textContent = text;
}

function appendMsg(agent, content) {
  const div = document.createElement("div");
  div.className = "msg";
  div.innerHTML = '<span class="agent">' + agent + "</span>" + content;
  chatEl.appendChild(div);
  chatEl.scrollTop = chatEl.scrollHeight;
}

function renderDrafts(drafts) {
  draftsEl.innerHTML = "";
  drafts.forEach((draft) => {
    const card = document.createElement("article");
    card.className = "draft-item";
    card.innerHTML = "<h3>" + draft.name + "</h3><p>" + draft.draft + "</p>";
    draftsEl.appendChild(card);
  });
}

function renderRetrieval(items) {
  retrievalEl.innerHTML = "";
  items.forEach((item) => {
    const li = document.createElement("li");
    li.textContent = item.title + ": " + (item.snippet || "");
    retrievalEl.appendChild(li);
  });
}

async function startSession(question) {
  const resp = await fetch("/api/session/start", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question }),
  });
  if (resp.status === 429) {
    throw new Error("并发会话过多，请稍后再试");
  }
  if (!resp.ok) {
    throw new Error("启动失败: " + resp.status);
  }
  return resp.json();
}

async function fetchEvents(sessionId, cursor) {
  const resp = await fetch("/api/session/" + sessionId + "/events?cursor=" + cursor);
  if (!resp.ok) {
    throw new Error("拉取事件失败: " + resp.status);
  }
  return resp.json();
}

// 终态现在有成功、失败、超时三种。后端明确给出 status，
// 所以这里不再只靠 done 判断结果，也不会再出现「一直转圈且不给任何提示」。
function describeOutcome(data) {
  if (data.status === "succeeded") {
    setStatus("已完成：总控已提交最终方案。");
    return true;
  }
  if (data.status === "failed") {
    appendMsg("系统", "执行失败：" + (data.error || "后端未给出原因"));
    setStatus("执行失败，请查看后端日志。");
    return true;
  }
  if (data.status === "expired") {
    appendMsg("系统", "会话超时：" + (data.error || "长时间无进展"));
    setStatus("会话已超时，请重新提交。");
    return true;
  }
  return false;
}

runBtn.addEventListener("click", async () => {
  const question = questionInput.value.trim();
  if (!question) {
    alert("请先输入问题");
    return;
  }

  runBtn.disabled = true;
  retrievalEl.innerHTML = "";
  draftsEl.innerHTML = "";
  chatEl.innerHTML = "";
  finalPlanEl.textContent = "";

  try {
    setStatus("正在创建协同会话...");
    const startBody = await startSession(question);
    const sessionId = startBody.session_id;
    let cursor = 0;
    let finished = false;

    while (!finished) {
      const data = await fetchEvents(sessionId, cursor);
      cursor = data.next_cursor;

      data.events.forEach((event) => {
        if (event.type === "stage") {
          if (event.status === "start") {
            setStatus(event.label + "...");
          }
          return;
        }
        if (event.type === "retrieval") {
          const meta = event.meta || {};
          if (meta.source === "mock") {
            setStatus("未连接知识库，使用模拟数据...");
          }
          renderRetrieval(event.payload);
        }
        if (event.type === "five_focus_drafts") {
          renderDrafts(event.payload);
        }
        if (event.type === "chat") {
          appendMsg(event.payload.agent, event.payload.content);
        }
        if (event.type === "final_solution") {
          finalPlanEl.textContent = event.payload;
        }
      });

      finished = describeOutcome(data);
      if (!finished) {
        await new Promise((resolve) => setTimeout(resolve, 250));
      }
    }
  } catch (err) {
    appendMsg("系统", "出错：" + err.message);
    setStatus("执行失败，请检查后端日志。");
  } finally {
    runBtn.disabled = false;
  }
});
