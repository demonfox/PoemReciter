(() => {
    let currentPoem = null;

    const poemHeaderEl = document.getElementById("poem-header");
    const poemMetaEl = document.getElementById("poem-meta");
    const reciteForm = document.getElementById("recite-form");
    const answerInput = document.getElementById("answer-input");
    const submitBtn = document.getElementById("submit-btn");
    const nextBtn = document.getElementById("next-btn");
    const resultSection = document.getElementById("result-section");
    const resultBanner = document.getElementById("result-banner");
    const comparisonBox = document.getElementById("comparison-box");
    const expectedTextEl = document.getElementById("expected-text");
    const submittedTextEl = document.getElementById("submitted-text");
    const lineDiffBox = document.getElementById("line-diff-box");
    const lineDiffList = document.getElementById("line-diff-list");

    function resetResultView() {
        resultSection.classList.add("hidden");
        comparisonBox.classList.add("hidden");
        lineDiffBox.classList.add("hidden");
        resultBanner.textContent = "";
        resultBanner.className = "result-banner";
        expectedTextEl.textContent = "";
        submittedTextEl.textContent = "";
        lineDiffList.innerHTML = "";
    }

    async function loadRandomPoem() {
        submitBtn.disabled = true;
        nextBtn.disabled = true;
        resetResultView();

        const query = currentPoem ? `?exclude=${encodeURIComponent(currentPoem.id)}` : "";
        try {
            const response = await fetch(`/api/poems/random${query}`);
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            currentPoem = await response.json();
            poemHeaderEl.textContent = currentPoem.header;
            poemMetaEl.textContent = currentPoem.line_count
                ? `共 ${currentPoem.line_count} 句`
                : "";
            answerInput.value = "";
            answerInput.rows = Math.max(4, Math.min(12, (currentPoem.line_count || 4) + 1));
            answerInput.focus();
        } catch (err) {
            poemHeaderEl.textContent = "加载失败，请刷新页面重试";
            poemMetaEl.textContent = "";
        } finally {
            submitBtn.disabled = false;
            nextBtn.disabled = false;
        }
    }

    async function submitAnswer(event) {
        if (event) {
            event.preventDefault();
        }
        if (!currentPoem) {
            return;
        }

        submitBtn.disabled = true;
        try {
            const response = await fetch(`/api/poems/${currentPoem.id}/check`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ answer: answerInput.value }),
            });
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            const result = await response.json();
            renderResult(result);
        } catch (err) {
            resultSection.classList.remove("hidden");
            resultBanner.className = "result-banner incorrect";
            resultBanner.textContent = "提交核对失败，请重试。";
        } finally {
            submitBtn.disabled = false;
        }
    }

    function renderResult(result) {
        resultSection.classList.remove("hidden");

        if (result.is_correct) {
            resultBanner.className = "result-banner correct";
            resultBanner.textContent = "正确！";
            comparisonBox.classList.add("hidden");
            lineDiffBox.classList.add("hidden");
            return;
        }

        resultBanner.className = "result-banner incorrect";
        resultBanner.textContent = "错误！请对照原诗检查：";

        expectedTextEl.textContent = result.expected_text;
        submittedTextEl.textContent = result.submitted_text || "（未输入内容）";
        comparisonBox.classList.remove("hidden");

        lineDiffList.innerHTML = "";
        if (Array.isArray(result.line_comparisons) && result.line_comparisons.length > 0) {
            for (const item of result.line_comparisons) {
                const li = document.createElement("li");
                li.className = `line-diff-item ${item.is_correct ? "match" : "mismatch"}`;
                if (item.is_correct) {
                    li.textContent = `第 ${item.line_number} 句：✓ ${item.expected}`;
                } else {
                    const actualDisplay = item.actual || "（空）";
                    li.textContent = `第 ${item.line_number} 句：✗ 您的输入「${actualDisplay}」 → 原句「${item.expected || "（无此句）"}」`;
                }
                lineDiffList.appendChild(li);
            }
            lineDiffBox.classList.remove("hidden");
        }
    }

    reciteForm.addEventListener("submit", submitAnswer);
    nextBtn.addEventListener("click", loadRandomPoem);

    answerInput.addEventListener("keydown", (event) => {
        if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
            submitAnswer(event);
        }
    });

    loadRandomPoem();
})();

