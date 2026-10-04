/* Cointy Pay Frontend */

const API_BASE = "https://cointy-pay.onrender.com";

const tg = window.Telegram?.WebApp;

if (tg) {
  tg.ready();
  tg.expand();

  tg.setHeaderColor?.("#06140f");
  tg.setBackgroundColor?.("#06140f");
}


const state = {
  user: null,
  tasks: [],
  completed: new Set(),
  history: []
};


function $(id) {
  return document.getElementById(id);
}


function showNotice(message, error = false) {

  const el = $("notice");

  if (!el) return;

  el.textContent = message;

  el.classList.remove("hidden", "error");

  if (error) {
    el.classList.add("error");
  }
}


function hideNotice() {

  const el = $("notice");

  if (el) {
    el.classList.add("hidden");
  }
}


async function api(path, options = {}) {

  const headers = {
    "Content-Type": "application/json",
    ...(options.headers || {})
  };

  const res = await fetch(
    API_BASE + path,
    {
      ...options,
      headers
    }
  );

  const data = await res.json().catch(() => ({
    detail: "Invalid server response"
  }));

  if (!res.ok) {
    throw new Error(data.detail || "Request failed");
  }

  return data;
}


function initData() {
  return tg?.initData || "";
}


/* ==============================
   FORCE JOIN CHECK
============================== */

async function checkJoinStatus() {

  if (!initData()) {
    throw new Error(
      "Open Cointy Pay from inside Telegram."
    );
  }

  return await api(
    "/api/join-status",
    {
      method: "POST",
      body: JSON.stringify({
        init_data: initData()
      })
    }
  );
}


/* ==============================
   LOAD APP
============================== */

async function load() {

  if (!initData()) {

    showNotice(
      "Open Cointy Pay from inside Telegram.",
      true
    );

    return;
  }


  try {

    const join = await checkJoinStatus();


    /* User has not joined */

    if (!join.joined) {

      $("joinGate").style.display = "flex";

      return;
    }


    /* User has joined */

    $("joinGate").style.display = "none";


    const data = await api(
      "/api/me",
      {
        method: "POST",
        body: JSON.stringify({
          init_data: initData()
        })
      }
    );


    state.user = data.user;

    state.completed = new Set(
      data.completed
    );


    $("points").textContent =
      data.user.points;

    $("completed").textContent =
      state.completed.size;


    const taskData =
      await api("/api/tasks");


    state.tasks =
      taskData.tasks;


    renderTasks();

    await loadHistory();

    hideNotice();

  } catch (e) {

    showNotice(
      e.message || "Something went wrong.",
      true
    );
  }
}


/* ==============================
   RENDER TASKS
============================== */

function renderTasks() {

  const taskBox = $("tasks");

  if (!taskBox) return;


  taskBox.innerHTML =
    state.tasks.map(t => {

      const done =
        state.completed.has(t.id);


      return `
        <article class="task">

          <div class="task-icon">
            ${t.id}
          </div>

          <div class="task-main">

            <strong>
              ${t.title}
            </strong>

            <span>
              ${done ? "Completed" : "Available task"}
              • SmartLink
            </span>

          </div>

          <button
            ${done ? "disabled" : ""}
            data-task="${t.id}"
          >
            ${done ? "Done" : "Open"}
          </button>

        </article>
      `;

    }).join("");


  document
    .querySelectorAll("[data-task]")
    .forEach(button => {

      button.addEventListener(
        "click",
        () => {
          openTask(
            Number(button.dataset.task)
          );
        }
      );

    });
}


/* ==============================
   OPEN TASK
============================== */

async function openTask(taskId) {

  try {

    if (
      typeof show_11955158 !== "function"
    ) {

      showNotice(
        "Monetag ad is not ready. Please try again.",
        true
      );

      return;
    }


    await show_11955158();


    const result =
      await api(
        "/api/tasks/click",
        {
          method: "POST",

          body: JSON.stringify({
            init_data: initData(),
            task_id: taskId
          })
        }
      );


    if (result.url) {

      if (tg?.openLink) {

        tg.openLink(result.url);

      } else {

        window.open(
          result.url,
          "_blank",
          "noopener,noreferrer"
        );

      }
    }


    showNotice("Task opened.");


    state.completed.add(taskId);

    $("completed").textContent =
      state.completed.size;


    renderTasks();


  } catch (e) {

    console.error(
      "Monetag error:",
      e
    );

    showNotice(
      "Ad could not be loaded. Please try again.",
      true
    );
  }
}


/* ==============================
   WITHDRAWAL HISTORY
============================== */

async function loadHistory() {

  try {

    const data =
      await api(
        "/api/withdrawals",
        {
          method: "POST",

          body: JSON.stringify({
            init_data: initData()
          })
        }
      );


    state.history =
      data.items || [];


    $("history").innerHTML =
      state.history.length

        ? state.history.map(x => `
            <div class="history-item">

              <span>
                ৳${x.amount_bdt}
                • ${x.method}
              </span>

              <span class="status">
                ${x.status}
              </span>

            </div>
          `).join("")

        : "<p class='muted'>No withdrawals yet.</p>";


  } catch (e) {

    $("history").innerHTML =
      "<p class='muted'>History unavailable.</p>";
  }
}


/* ==============================
   TABS
============================== */

document
  .querySelectorAll(".tab")
  .forEach(tab => {

    tab.addEventListener(
      "click",
      () => {

        document
          .querySelectorAll(".tab")
          .forEach(x =>
            x.classList.remove("active")
          );


        tab.classList.add("active");


        [
          "tasks",
          "wallet",
          "history"
        ].forEach(x => {

          $(x + "Tab")
            .classList
            .toggle(
              "hidden",
              x !== tab.dataset.tab
            );

        });

      }
    );

  });


/* ==============================
   WITHDRAW
============================== */

$("withdrawForm")
  .addEventListener(
    "submit",
    async e => {

      e.preventDefault();


      try {

        const data =
          await api(
            "/api/withdraw",
            {
              method: "POST",

              body: JSON.stringify({

                init_data:
                  initData(),

                method:
                  $("method").value,

                account:
                  $("account")
                    .value
                    .trim()

              })
            }
          );


        showNotice(
          `Withdrawal ${data.id} submitted for review.`
        );


        $("account").value = "";


        await load();


      } catch (e) {

        showNotice(
          e.message,
          true
        );

      }

    }
  );


/* ==============================
   CLOSE BUTTON
============================== */

$("closeBtn")
  .addEventListener(
    "click",
    () => tg?.close?.()
  );


/* ==============================
   CHECK JOIN BUTTON
============================== */

$("checkJoinBtn")
  .addEventListener(
    "click",
    async () => {

      const btn =
        $("checkJoinBtn");

      const msg =
        $("joinMessage");


      btn.disabled = true;

      btn.textContent =
        "Checking...";

      msg.textContent =
        "Checking channel membership...";


      try {

        const result =
          await checkJoinStatus();


        if (result.joined) {

          msg.textContent =
            "✅ Membership verified!";


          $("joinGate")
            .style
            .display = "none";


          await load();


        } else {

          msg.textContent =
            "❌ Please join the channel first.";

        }


      } catch (e) {

        console.error(e);

        msg.textContent =
          "⚠️ Verification failed. Please try again.";

      }


      btn.disabled = false;

      btn.textContent =
        "✅ Check Joined";

    }
  );


/* ==============================
   START
============================== */

load();
