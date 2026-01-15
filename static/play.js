// static/play.js
(() => {
  const game = document.querySelector(".game-wrap");
  if (!game) return;

  const puzzleStr = game.dataset.puzzle || "";
  const solutionStr = game.dataset.solution || "";
  const cellPx = parseInt(game.dataset.cellpx || "34", 10);
  const maxMistakes = parseInt(game.dataset.maxmistakes || "3", 10);

  const boardEl = document.getElementById("board");
  const timerEl = document.getElementById("timer");
  const mistakesEl = document.getElementById("mistakes");

  if (!boardEl || puzzleStr.length !== 81 || solutionStr.length !== 81) {
    console.warn("Board/puzzle/solution ontbreekt of is ongeldig.");
    return;
  }

  // ---------- State ----------
  let selected = null; // index 0..80
  let started = false;
  let startTime = 0;
  let timerId = null;
  let mistakes = 0;

  // base puzzle & current entries
  const givens = puzzleStr.split("").map(ch => ch !== "0"); // true als gegeven
  let values = puzzleStr.split("").map(ch => (ch === "0" ? "" : ch)); // string digits

  // ---------- Timer ----------
  function formatTime(sec) {
    const m = Math.floor(sec / 60);
    const s = sec % 60;
    return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
  }

  function tick() {
    const sec = Math.floor((Date.now() - startTime) / 1000);
    if (timerEl) timerEl.textContent = formatTime(sec);
  }

  function startTimerIfNeeded() {
    if (started) return;
    started = true;
    startTime = Date.now();
    timerId = setInterval(tick, 250);
    tick();
  }

  function stopTimer() {
    if (timerId) clearInterval(timerId);
    timerId = null;
  }

  // ---------- Helpers ----------
  function rcFromIndex(i) {
    return { r: Math.floor(i / 9), c: i % 9 };
  }

  function isCorrect(i, val) {
    return solutionStr[i] === val;
  }

  function setMistakes(n) {
    mistakes = n;
    if (mistakesEl) mistakesEl.textContent = String(mistakes);
  }

  function clampMistakes() {
    if (mistakes >= maxMistakes) {
      // lock input
      boardEl.classList.add("locked");
      document.querySelectorAll(".pad-btn").forEach(b => b.disabled = true);
      stopTimer();
      alert("Je hebt 3 fouten gemaakt. Probeer opnieuw!");
    }
  }

  function checkWin() {
    for (let i = 0; i < 81; i++) {
      if (values[i] === "" || values[i] !== solutionStr[i]) return false;
    }
    stopTimer();
    setTimeout(() => alert("🎉 Goed gedaan! Sudoku opgelost."), 50);
    return true;
  }

  // ---------- Render ----------
  boardEl.style.setProperty("--cell", `${cellPx}px`);
  boardEl.innerHTML = "";

  const cells = [];
  for (let i = 0; i < 81; i++) {
    const cell = document.createElement("div");
    cell.className = "cell2";
    cell.tabIndex = 0;
    cell.dataset.i = String(i);

    const ch = values[i];
    if (ch) cell.textContent = ch;

    if (givens[i]) cell.classList.add("given");

    // thick borders like sudoku
    const { r, c } = rcFromIndex(i);
    if (c === 2 || c === 5) cell.classList.add("thick-right");
    if (r === 2 || r === 5) cell.classList.add("thick-bottom");

    cell.addEventListener("click", () => selectCell(i));
    cells.push(cell);
    boardEl.appendChild(cell);
  }

  function clearHighlights() {
    cells.forEach(c => c.classList.remove("selected", "same", "rc", "bad"));
  }

  function applyHighlights() {
    clearHighlights();
    if (selected === null) return;

    const { r: sr, c: sc } = rcFromIndex(selected);
    const selVal = values[selected];

    cells[selected].classList.add("selected");

    // highlight row/col
    for (let i = 0; i < 81; i++) {
      const { r, c } = rcFromIndex(i);
      if (r === sr || c === sc) cells[i].classList.add("rc");
    }

    // highlight same numbers
    if (selVal) {
      for (let i = 0; i < 81; i++) {
        if (values[i] === selVal) cells[i].classList.add("same");
      }
    }

    // mark wrong entries red (only for non-empty user entries)
    for (let i = 0; i < 81; i++) {
      if (!givens[i] && values[i] && values[i] !== solutionStr[i]) {
        cells[i].classList.add("bad");
      }
    }
  }

  function selectCell(i) {
    selected = i;
    applyHighlights();
    cells[i].focus();
  }

  // ---------- Input ----------
  function setValueAt(i, val) {
    if (i === null) return;
    if (givens[i]) return;
    if (boardEl.classList.contains("locked")) return;

    if (val === "") {
      values[i] = "";
      cells[i].textContent = "";
      applyHighlights();
      return;
    }

    // start timer on first input
    startTimerIfNeeded();

    values[i] = val;
    cells[i].textContent = val;

    // if wrong -> count mistake (+ make red)
    if (!isCorrect(i, val)) {
      setMistakes(mistakes + 1);
      applyHighlights();
      clampMistakes();
      return;
    }

    applyHighlights();
    checkWin();
  }

  // keyboard
  document.addEventListener("keydown", (e) => {
    if (selected === null) return;

    const key = e.key;

    if (key >= "1" && key <= "9") {
      e.preventDefault();
      setValueAt(selected, key);
      return;
    }

    if (key === "Backspace" || key === "Delete" || key === "0") {
      e.preventDefault();
      setValueAt(selected, "");
      return;
    }

    // arrows
    const { r, c } = rcFromIndex(selected);
    if (key === "ArrowLeft" && c > 0) return selectCell(selected - 1);
    if (key === "ArrowRight" && c < 8) return selectCell(selected + 1);
    if (key === "ArrowUp" && r > 0) return selectCell(selected - 9);
    if (key === "ArrowDown" && r < 8) return selectCell(selected + 9);
  });

  // pad buttons
  document.querySelectorAll(".pad-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      const num = btn.dataset.num;
      const action = btn.dataset.action;
      if (action === "erase") setValueAt(selected, "");
      else if (action === "reset") resetGame();
      else if (num) setValueAt(selected, num);
    });
  });

  function resetGame() {
    values = puzzleStr.split("").map(ch => (ch === "0" ? "" : ch));
    for (let i = 0; i < 81; i++) {
      cells[i].textContent = values[i] || "";
    }
    selected = null;
    setMistakes(0);
    boardEl.classList.remove("locked");
    document.querySelectorAll(".pad-btn").forEach(b => b.disabled = false);

    // timer reset
    stopTimer();
    started = false;
    if (timerEl) timerEl.textContent = "00:00";
    applyHighlights();
  }

  // init UI
  if (timerEl) timerEl.textContent = "00:00";
  if (mistakesEl) mistakesEl.textContent = "0";

  // select first empty cell
  const firstEmpty = values.findIndex(v => v === "");
  if (firstEmpty >= 0) selectCell(firstEmpty);
  else selectCell(0);
})();
