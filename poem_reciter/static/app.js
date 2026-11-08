(() => {
    let currentPoem = null;
    let currentGroupBy = "poem";

    const poemHeaderEl = document.getElementById("poem-header");
    const poemMetaEl = document.getElementById("poem-meta");
    const reciteForm = document.getElementById("recite-form");
    const answerInput = document.getElementById("answer-input");
    const submitBtn = document.getElementById("submit-btn");
    const nextBtn = document.getElementById("next-btn");
    const resultSection = document.getElementById("result-section");
    const resultBanner = document.getElementById("result-banner");
    const poemRollingStatsEl = document.getElementById("poem-rolling-stats");
    const comparisonBox = document.getElementById("comparison-box");
    const expectedTextEl = document.getElementById("expected-text");
    const submittedTextEl = document.getElementById("submitted-text");
    const lineDiffBox = document.getElementById("line-diff-box");
    const lineDiffList = document.getElementById("line-diff-list");

    const statsSummaryTextEl = document.getElementById("stats-summary-text");
    const recitedOnlyToggle = document.getElementById("recited-only-toggle");
    const statsTabs = document.querySelectorAll(".stats-tab");
    const statsTableHeadRow = document.getElementById("stats-table-head-row");
    const statsTableBody = document.getElementById("stats-table-body");

    function formatPct(value) {
        if (value === null || value === undefined || Number.isNaN(value)) {
            return "—";
        }
        return `${(value * 100).toFixed(1)}%`;
    }

    function formatPoemPromptMeta(poem) {
        const parts = [];
        if (poem.line_count) {
            parts.push(`共 ${poem.line_count} 句`);
        }
        if (poem.char_count) {
            parts.push(`${poem.char_count} 字`);
        }
        if (poem.poem_stats && poem.poem_stats.attempt_count > 0) {
            const st = poem.poem_stats;
            parts.push(`已背 ${st.attempt_count} 次（平均正确率 ${formatPct(st.avg_accuracy)}）`);
        } else {
            parts.push("尚未背诵");
        }
        return parts.join(" · ");
    }

    function resetResultView() {
        resultSection.classList.add("hidden");
        poemRollingStatsEl.classList.add("hidden");
        comparisonBox.classList.add("hidden");
        lineDiffBox.classList.add("hidden");
        resultBanner.textContent = "";
        resultBanner.className = "result-banner";
        poemRollingStatsEl.textContent = "";
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
            poemMetaEl.textContent = formatPoemPromptMeta(currentPoem);
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
            if (result.poem_stats && currentPoem) {
                currentPoem.poem_stats = result.poem_stats;
                poemMetaEl.textContent = formatPoemPromptMeta(currentPoem);
            }
            renderResult(result);
            loadStats();
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

        const totalChars = result.total_chars ?? 0;
        const correctChars = result.correct_chars ?? 0;
        const wrongChars = result.wrong_chars ?? 0;
        const extraChars = result.extra_chars ?? 0;
        const accuracyText = formatPct(result.accuracy ?? (result.is_correct ? 1 : 0));
        const extraNote = extraChars > 0 ? `，多写 ${extraChars} 字（已倒扣）` : "";

        if (result.poem_stats) {
            const st = result.poem_stats;
            poemRollingStatsEl.textContent =
                `本诗累计背诵 ${st.attempt_count} 次（全对 ${st.perfect_count} 次） · ` +
                `平均正确率 ${formatPct(st.avg_accuracy)} · ` +
                `累计字数正确率 ${formatPct(st.char_accuracy)}（${st.correct_chars}/${st.total_chars} 字）`;
            poemRollingStatsEl.classList.remove("hidden");
        }

        if (result.is_correct) {
            resultBanner.className = "result-banner correct";
            resultBanner.textContent = `正确！本次正确率 ${accuracyText}（对 ${correctChars}/${totalChars} 字）`;
            comparisonBox.classList.add("hidden");
            lineDiffBox.classList.add("hidden");
            return;
        }

        resultBanner.className = "result-banner incorrect";
        resultBanner.textContent =
            `本次正确率 ${accuracyText}（共 ${totalChars} 字：对 ${correctChars} 字，错/漏 ${wrongChars} 字${extraNote}）`;

        expectedTextEl.textContent = result.expected_text;
        submittedTextEl.textContent = result.submitted_text || "（未输入内容）";
        comparisonBox.classList.remove("hidden");

        lineDiffList.innerHTML = "";
        if (Array.isArray(result.line_comparisons) && result.line_comparisons.length > 0) {
            for (const item of result.line_comparisons) {
                const li = document.createElement("li");
                li.className = `line-diff-item ${item.is_correct ? "match" : "mismatch"}`;
                const lineTotal = item.total_chars ?? 0;
                const lineCorrect = item.correct_chars ?? 0;
                const lineExtra = item.extra_chars ?? 0;
                const scoreTag = lineTotal > 0
                    ? `（对 ${lineCorrect}/${lineTotal} 字${lineExtra > 0 ? `，多写 ${lineExtra} 字` : ""}）`
                    : `（多出整行 ${lineExtra} 字）`;

                if (item.is_correct) {
                    li.textContent = `第 ${item.line_number} 句：✓ ${item.expected} ${scoreTag}`;
                } else {
                    const actualDisplay = item.actual || "（空）";
                    li.textContent =
                        `第 ${item.line_number} 句：✗ 您的输入「${actualDisplay}」 → 原句「${item.expected || "（无此句）"}」 ${scoreTag}`;
                }
                lineDiffList.appendChild(li);
            }
            lineDiffBox.classList.remove("hidden");
        }
    }

    async function loadStats() {
        const recitedOnly = recitedOnlyToggle && recitedOnlyToggle.checked ? "1" : "0";
        try {
            const response = await fetch(
                `/api/stats?group_by=${encodeURIComponent(currentGroupBy)}&recited_only=${recitedOnly}`
            );
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            const data = await response.json();
            renderStats(data);
        } catch (err) {
            if (statsSummaryTextEl) {
                statsSummaryTextEl.textContent = "统计数据加载失败";
            }
        }
    }

    function renderStats(data) {
        const s = data.summary || {};
        if (statsSummaryTextEl) {
            if (s.attempt_count > 0) {
                statsSummaryTextEl.textContent =
                    `已背 ${s.recited_poems}/${s.total_poems} 首 · 累计背诵 ${s.attempt_count} 次（全对 ${s.perfect_count} 次） · ` +
                    `整体平均正确率 ${formatPct(s.avg_accuracy)} · 累计字数正确率 ${formatPct(s.char_accuracy)}（${s.correct_chars}/${s.total_chars} 字）`;
            } else {
                statsSummaryTextEl.textContent = `共收录 ${s.total_poems || 0} 首诗词 · 暂无背诵记录`;
            }
        }

        if (!statsTableHeadRow || !statsTableBody) {
            return;
        }

        if (currentGroupBy === "poem") {
            statsTableHeadRow.innerHTML = `
                <th>诗词</th>
                <th>背诵次数</th>
                <th>平均正确率 (B)</th>
                <th>累计字数正确率 (A)</th>
            `;
        } else if (currentGroupBy === "author") {
            statsTableHeadRow.innerHTML = `
                <th>作者</th>
                <th>已背/总首数</th>
                <th>背诵次数</th>
                <th>平均正确率 (B)</th>
                <th>累计字数正确率 (A)</th>
            `;
        } else {
            statsTableHeadRow.innerHTML = `
                <th>朝代</th>
                <th>已背/总首数</th>
                <th>背诵次数</th>
                <th>平均正确率 (B)</th>
                <th>累计字数正确率 (A)</th>
            `;
        }

        const items = data.items || [];
        const colSpan = currentGroupBy === "poem" ? 4 : 5;
        if (items.length === 0) {
            statsTableBody.innerHTML = `<tr><td colspan="${colSpan}" class="stats-empty">暂无符合条件的背诵记录</td></tr>`;
            return;
        }

        statsTableBody.innerHTML = "";
        for (const item of items) {
            const tr = document.createElement("tr");
            const avgAccText = formatPct(item.avg_accuracy);
            const charAccText = item.attempt_count > 0
                ? `${formatPct(item.char_accuracy)}（${item.correct_chars}/${item.total_chars} 字）`
                : "—";
            const attemptText = item.attempt_count > 0
                ? `${item.attempt_count} 次（全对 ${item.perfect_count}）`
                : "0 次";

            if (currentGroupBy === "poem") {
                tr.innerHTML = `
                    <td>${item.header} <span class="accuracy-secondary">(${item.char_count}字)</span></td>
                    <td>${attemptText}</td>
                    <td class="accuracy-primary">${avgAccText}</td>
                    <td class="accuracy-secondary">${charAccText}</td>
                `;
            } else if (currentGroupBy === "author") {
                const label = item.dynasty ? `【${item.dynasty}】${item.key}` : item.key;
                tr.innerHTML = `
                    <td>${label}</td>
                    <td>${item.recited_poems} / ${item.total_poems} 首</td>
                    <td>${attemptText}</td>
                    <td class="accuracy-primary">${avgAccText}</td>
                    <td class="accuracy-secondary">${charAccText}</td>
                `;
            } else {
                tr.innerHTML = `
                    <td>${item.key}</td>
                    <td>${item.recited_poems} / ${item.total_poems} 首</td>
                    <td>${attemptText}</td>
                    <td class="accuracy-primary">${avgAccText}</td>
                    <td class="accuracy-secondary">${charAccText}</td>
                `;
            }
            statsTableBody.appendChild(tr);
        }
    }

    for (const tab of statsTabs) {
        tab.addEventListener("click", () => {
            currentGroupBy = tab.dataset.groupBy || "poem";
            for (const t of statsTabs) {
                const isActive = t === tab;
                t.classList.toggle("active", isActive);
                t.setAttribute("aria-selected", isActive ? "true" : "false");
            }
            loadStats();
        });
    }

    if (recitedOnlyToggle) {
        recitedOnlyToggle.addEventListener("change", loadStats);
    }

    reciteForm.addEventListener("submit", submitAnswer);
    nextBtn.addEventListener("click", loadRandomPoem);

    answerInput.addEventListener("keydown", (event) => {
        if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
            submitAnswer(event);
        }
    });

    loadRandomPoem();
    loadStats();
})();
