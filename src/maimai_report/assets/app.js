(() => {
  "use strict";

  const raw = document.getElementById("report-data")?.textContent || "{}";
  const data = JSON.parse(raw);
  const jackets = JSON.parse(document.getElementById("jacket-data")?.textContent || "{}");
  const download = JSON.parse(document.getElementById("download-data")?.textContent || "{}");
  const app = document.getElementById("app");

  const presentNum = value => value == null ? "—" : num(value);
  const presentPct = value => value == null ? "—" : pct(value);
  const palette = ["#ff4f98", "#18cfe0", "#ffcf32", "#7566ff", "#20c79a"];
  const safe = (value) => String(value ?? "").replace(/[&<>'"]/g, (char) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;"
  }[char]));
  const num = (value) => Number(value || 0).toLocaleString("en-US");
  const signed = (value) => `${Number(value || 0) > 0 ? "+" : ""}${num(value || 0)}`;
  const pct = (value, digits = 4) => Number(value || 0).toFixed(digits) + "%";
  const clamp = (value, min, max) => Math.max(min, Math.min(max, value));
  const rate = (item) => Number(item?.rate || 0);
  const gain = (item) => rate(item) - Number(item?.previousRate || 0);

  const player = data.player || { displayName: "Player", username: "player", timezone: "UTC", game: "maimai DX" };
  const before = data.before || {};
  const after = data.after || {};
  const delta = data.delta || {};
  const session = data.session || {};
  const sessionScores = Array.isArray(session.scores) ? session.scores : [];
  const changedPBs = Array.isArray(session.changedPBs) ? session.changedPBs : [];
  const hasSession = changedPBs.length > 0 || sessionScores.length > 0 || Number(delta.reconstructedRating || 0) !== 0;

  function timeRange() {
    const allTimes = sessionScores.map((x) => x.timeAchieved).filter(Number.isFinite);
    const start = Number(session.startTimeAchieved || (allTimes.length ? Math.min(...allTimes) : 0));
    const end = Number(session.endTimeAchieved || (allTimes.length ? Math.max(...allTimes) : 0));
    const generated = Date.parse(data.generatedAt || new Date().toISOString());
    const zone = player.timezone || "UTC";
    const date = new Intl.DateTimeFormat("en-US", { timeZone: zone, weekday: "long", month: "long", day: "numeric", year: "numeric" }).format(new Date(end || generated));
    if (!start || !end) return date;
    const tf = new Intl.DateTimeFormat("en-US", { timeZone: zone, hour: "numeric", minute: "2-digit" });
    return `${date} • ${tf.format(new Date(start))}–${tf.format(new Date(end))}`;
  }

  function durationText() {
    const times = sessionScores.map((x) => x.timeAchieved).filter(Number.isFinite);
    const start = Number(session.startTimeAchieved || (times.length ? Math.min(...times) : 0));
    const end = Number(session.endTimeAchieved || (times.length ? Math.max(...times) : 0));
    if (!start || !end || end < start) return "synced session";
    const mins = Math.max(1, Math.round((end - start) / 60000));
    const h = Math.floor(mins / 60);
    const m = mins % 60;
    return h ? `${h}h ${m}m session` : `${m}m session`;
  }

  function diffClass(difficulty = "") {
    const d = String(difficulty).toLowerCase();
    if (d.includes("re:master") || d.includes("remaster")) return "diff-remaster";
    if (d.includes("master")) return "diff-master";
    if (d.includes("expert")) return "diff-expert";
    if (d.includes("advanced")) return "diff-advanced";
    if (d.includes("basic")) return "diff-basic";
    return "diff-unknown";
  }

  const gradeOrder = ["SSS+", "SSS", "SS+", "SS", "S+", "S", "AAA", "AA", "A", "BBB", "BB", "B", "C", "D"];
  const gradeIndex = (grade) => gradeOrder.includes(grade) ? gradeOrder.indexOf(grade) : gradeOrder.length;
  function gradeHtml(grade) {
    const value = String(grade || "—");
    const kind = /^SSS/.test(value) ? "rainbow" : /^S/.test(value) ? "gold" : /^A/.test(value) ? "red" : /^B/.test(value) ? "blue" : "unknown";
    return `<span class="grade-pill grade-${kind}">${kind==="rainbow"?[...value].map(letter=>`<span>${safe(letter)}</span>`).join(""):safe(value)}</span>`;
  }

  function chartBadge(item) {
    const d = String(item.difficulty || "");
    const name = d.replace(/^(DX|Standard|Std)\s+/i, "") || "Unknown";
    return `<span class="chart-identity"><span class="difficulty-pill ${diffClass(d)}">${safe(name)} <b>${safe(item.level || "—")}</b></span><span class="chart-format">${/^DX\s/i.test(d) ? "DX" : "STD"}</span></span>`;
  }

  function jacketHtml(item) {
    const image = jackets[item.songID];
    return typeof image === "string" && /^data:image\/(png|jpeg|webp);base64,/.test(image)
      ? `<img class="song-jacket" src="${safe(image)}" alt="" width="56" height="56" loading="lazy" decoding="async" />`
      : `<span class="song-jacket jacket-missing" role="img" aria-label="Jacket unavailable"><span aria-hidden="true">♪</span><small aria-hidden="true">NO ART</small></span>`;
  }

  // Presentation tiers from SEGA's DX rating reference. Rating calculations are unchanged.
  const ratingTiers = [[0,"White"],[1000,"Blue"],[2000,"Green"],[4000,"Yellow"],[7000,"Red"],[10000,"Purple"],[12000,"Bronze"],[13000,"Silver"],[14000,"Gold"],[14500,"Platinum"],[15000,"Rainbow"],[16000,"Rainbow EX"]];
  function ratingTier(value) {
    const index = ratingTiers.findLastIndex(([floor]) => Number(value || 0) >= floor);
    const [floor, name] = ratingTiers[Math.max(0,index)];
    const next = ratingTiers[Math.max(0,index)+1];
    return {floor, name, next, key:name.toLowerCase().replace(/ /g,"-")};
  }

  function shortDifficulty(difficulty = "") {
    return String(difficulty).replace(/^DX\s+/i, "DX ").replace(/^Standard\s+/i, "Std ");
  }

  function story() {
    const emptyBefore = Math.max(0, 15 - Number(before.newSlotsFilled || 0));
    const emptyAfter = Math.max(0, 15 - Number(after.newSlotsFilled || 0));
    const newGain = Number(delta.new15Rating || 0);
    const oldGain = Number(delta.old35Rating || 0);
    const total = Number(delta.reconstructedRating || 0);

    if (!hasSession) return {
      title: "Your account was already fully synced.",
      copy: "No new MYT scores landed in this import. Run another explicit sync after your next play session.",
    };
    if (emptyBefore > 0 && emptyAfter === 0) return {
      title: `You filled ${emptyBefore} New 15 slot${emptyBefore === 1 ? "" : "s"} — then started attacking the floor.`,
      copy: `New 15 supplied ${signed(newGain)} rating, while Old 35 added ${signed(oldGain)}. The ${signed(total)} jump combined smart routing with real performance.`,
    };
    if (newGain > oldGain * 2) return {
      title: "Current-version charts drove the session.",
      copy: `Your New 15 moved ${signed(newGain)}, compared with ${signed(oldGain)} from Old 35. You are extracting much more value from the current song pool.`,
    };
    if (oldGain > newGain * 2) return {
      title: "This was an Old 35 refinement session.",
      copy: `Old 35 climbed ${signed(oldGain)} as stronger legacy scores replaced your floor. New 15 contributed ${signed(newGain)}.`,
    };
    return {
      title: "Balanced gains across both rating pools.",
      copy: `Old 35 added ${signed(oldGain)} and New 15 added ${signed(newGain)}, for ${signed(total)} overall.`,
    };
  }

  function difficultyBands() {
    const source = sessionScores.length ? sessionScores : changedPBs;
    const groups = new Map();
    for (const item of source) {
      const levelNum = Number(item.levelNum || parseFloat(item.level) || 0);
      const base = Math.floor(levelNum);
      const label = `${base} / ${base}+`;
      if (!groups.has(label)) groups.set(label, { label, base, items: [], rate: 0, percent: 0, fast: 0, slow: 0 });
      const g = groups.get(label);
      g.items.push(item);
      g.rate += rate(item);
      g.percent += Number(item.percent || 0);
      g.fast += Number(item.fast || 0);
      g.slow += Number(item.slow || 0);
    }
    const values = [...groups.values()].map((g) => ({
      ...g,
      count: g.items.length,
      avgRate: g.items.length ? g.rate / g.items.length : 0,
      avgPercent: g.items.length ? g.percent / g.items.length : 0,
    })).sort((a,b) => a.base - b.base);
    const best = values.reduce((winner, item) => !winner || item.avgRate > winner.avgRate ? item : winner, null);
    return { values, best };
  }

  function timingStats() {
    const source = sessionScores.length ? sessionScores : changedPBs;
    const fast = source.reduce((sum, x) => sum + Number(x.fast || 0), 0);
    const slow = source.reduce((sum, x) => sum + Number(x.slow || 0), 0);
    const total = fast + slow;
    const fastPct = total ? fast / total * 100 : 50;
    const diff = slow - fast;
    let label = "balanced";
    if (diff > Math.max(15, total * .12)) label = "slow-leaning";
    if (diff < -Math.max(15, total * .12)) label = "fast-leaning";
    return { fast, slow, total, fastPct, label };
  }

  function gradeCounts() {
    const source = sessionScores.length ? sessionScores : changedPBs;
    const counts = {};
    for (const item of source) counts[item.grade || "—"] = (counts[item.grade || "—"] || 0) + 1;
    return Object.entries(counts).sort((a,b) => gradeIndex(a[0]) - gradeIndex(b[0]) || a[0].localeCompare(b[0]));
  }

  function thresholdRate(levelNum, targetPercent) {
    const coeffs = targetPercent >= 100.5 ? 22.4 : targetPercent >= 100 ? 21.6 : targetPercent >= 99.5 ? 21.1 : targetPercent >= 99 ? 20.8 : targetPercent >= 98 ? 20.3 : targetPercent >= 97 ? 20.0 : 17.6;
    return Math.floor(Number(levelNum || 0) * Math.min(targetPercent, 100.5) / 100 * coeffs);
  }

  function quests() {
    const floor = Number(after.new15Floor || 0);
    const pool = Array.isArray(after.newPool) ? after.newPool : (Array.isArray(after.new15) ? after.new15 : []);
    const candidates = pool
      .filter((x) => Number(x.percent || 0) < 97 && 97 - Number(x.percent || 0) <= 2.5)
      .map((x) => {
        const projected = thresholdRate(x.levelNum, 97);
        const current = rate(x);
        const base = Math.max(current, floor);
        return { ...x, projected, estimatedGain: Math.max(0, projected - base), gap: 97 - Number(x.percent || 0) };
      })
      .filter((x) => x.estimatedGain > 0)
      .sort((a,b) => b.estimatedGain - a.estimatedGain || a.gap - b.gap)
      .slice(0, 2);

    const bands = difficultyBands();
    const out = candidates.map((x, i) => ({
      chart: x,
      icon: "♪",
      color: palette[i],
      title: x.title,
      sub: `${pct(x.percent)} → 97%`,
      reward: `+${x.estimatedGain} est.`,
      copy: `Reach the S threshold for a sharp coefficient jump on this ${safe(x.level)} chart.`,
    }));
    out.push({
      chart: (after.new15 || []).slice(-1)[0],
      icon: "◎", color: varColor("yellow"), title: (after.new15 || []).slice(-1)[0]?.title || "New 15 floor",
      sub: `Current floor ${floor}`, reward: "FLOOR",
      copy: "A fresh current-version chart above this value immediately improves your New 15.",
    });
    if (bands.best) out.push({
      icon: "★", color: varColor("purple"), title: `Explore current-version ${bands.best.label}`,
      sub: `Aim for 97–99%`, reward: `~${Math.round(bands.best.avgRate)} RT`,
      copy: "This was your best-performing difficulty band in the synced session sample.",
    });
    return out.slice(0,4);
  }

  function varColor(name) {
    return ({yellow:"#ffcf32", purple:"#7566ff", aqua:"#18cfe0", pink:"#ff4f98", mint:"#20c79a"})[name] || "#18cfe0";
  }



  function heroHtml() {
    const d = Number(delta.reconstructedRating || 0);
    const dateParts = timeRange().split(" • ");
    const tier = ratingTier(after.reconstructedRating);
    const previous = ratingTier(before.reconstructedRating);
    const progress = tier.next ? clamp((Number(after.reconstructedRating || 0)-tier.floor)/(tier.next[0]-tier.floor)*100,0,100) : 100;
    const ratingDigits = String(Math.trunc(Number(after.reconstructedRating || 0))).padStart(5, " ");
    return `<header class="session-header">
      <div class="scorecard-result">
        <div class="namecard tier-${tier.key}">
        <div class="namecard-identity"><h1>${safe(player.displayName || player.username)}</h1><strong class="namecard-tier">${tier.name}</strong></div>
        <div class="rating-plaque" role="img" aria-label="Reconstructed rating ${num(after.reconstructedRating)}"><strong class="rating-value" aria-hidden="true">${[...ratingDigits].map(digit=>`<span>${digit===" "?"":safe(digit)}</span>`).join("")}</strong></div>
        <div class="namecard-label"><span>Reconstructed rating</span><span class="session-change ${d<0?"negative":d===0?"flat":""}">${signed(d)}<span>this session</span></span></div>
        <div class="tier-progress" role="progressbar" aria-label="Progress through ${tier.name} rating tier" aria-valuenow="${Math.round(progress)}" aria-valuemin="0" aria-valuemax="100"><span style="width:${progress}%"></span></div><p class="tier-next">${previous.name!==tier.name && d>0 ? `<strong>${previous.name} → ${tier.name}</strong>` : `<strong>${num(tier.floor)}${tier.next?`–${num(tier.next[0]-1)}`:"+"}</strong>`}${tier.next?`<span>${num(tier.next[0]-Number(after.reconstructedRating||0))} to ${tier.next[1]}</span>`:""}</p></div>
        <div class="session-receipt"><p class="session-date">${safe(dateParts[0])}${dateParts[1] ? `<span>${safe(dateParts[1])}</span>` : ""}</p><p class="session-facts"><span><strong>${num(session.scoreCount ?? sessionScores.length)}</strong> plays</span><span><strong>${num(session.newPBCount ?? delta.pbCount)}</strong> new PBs</span><span>${safe(durationText().replace(/ session$/,""))}</span></p>
          <div class="contribution-heading"><h2>Rating gained</h2><button type="button" class="text-action" data-open-view="pools">Breakdown</button></div><div class="contributions"><div class="contribution old"><span>Old 35</span><strong class="${Number(delta.old35Rating)<0?"negative":""}">${signed(delta.old35Rating)}</strong></div><div class="contribution new"><span>New 15</span><strong class="${Number(delta.new15Rating)<0?"negative":""}">${signed(delta.new15Rating)}</strong></div></div>
        </div>
      </div>
    </header>`;
  }

  function bandsHtml() {
    const {values,best}=difficultyBands();
    if (!values.length) return `<p class="section-subtitle">No session score data available.</p>`;
    const order = ["diff-basic","diff-advanced","diff-expert","diff-master","diff-remaster","diff-unknown"];
    return `<div class="difficulty-breakdown">${values.map(g=>{
      const types = new Map();
      for (const x of g.items) {
        const key = `${x.difficulty}|${x.level}`;
        if (!types.has(key)) types.set(key,{...x,count:0,totalRate:0,totalPercent:0});
        const group = types.get(key); group.count++; group.totalRate+=rate(x); group.totalPercent+=Number(x.percent||0);
      }
      const rows = [...types.values()].sort((a,b)=>order.indexOf(diffClass(a.difficulty))-order.indexOf(diffClass(b.difficulty)) || Number(a.levelNum)-Number(b.levelNum) || String(a.difficulty).localeCompare(String(b.difficulty)));
      return `<section class="level-group"><div class="level-heading"><h3>Level ${safe(g.label)}</h3><span>${g.count} ${g.count===1?"play":"plays"} · ${g.avgRate.toFixed(1)} avg RT</span></div><p class="level-totals">All chart types: ${g.avgPercent.toFixed(2)}% average · ${g.fast} fast / ${g.slow} slow</p>${rows.map(x=>`<div class="difficulty-sample">${chartBadge(x)}<span>${x.count} ${x.count===1?"play":"plays"}</span><strong>${(x.totalPercent/x.count).toFixed(2)}%<small>${(x.totalRate/x.count).toFixed(1)} avg RT</small></strong></div>`).join("")}</section>`;
    }).join("")}</div>${best?`<p class="section-subtitle">Across chart types, level ${safe(best.label)} had the highest average return: ${best.avgRate.toFixed(1)} rating per chart.</p>`:""}`;
  }

  function timingHtml() {
    const t = timingStats();
    const max = Math.max(t.fast,t.slow,1);
    return `<div class="timing-summary"><p class="timing-balance">${safe(t.label.charAt(0).toUpperCase()+t.label.slice(1))}</p>
      <div class="timing-bars">
        <div class="timing-line"><span>Fast</span><div class="timing-track"><div class="timing-fill fast" style="width:${t.fast/max*100}%"></div></div><strong>${num(t.fast)}</strong></div>
        <div class="timing-line"><span>Slow</span><div class="timing-track"><div class="timing-fill slow" style="width:${t.slow/max*100}%"></div></div><strong>${num(t.slow)}</strong></div>
      </div><p class="section-subtitle">${t.label === "balanced" ? "Your timing distribution was broadly balanced across the session. No strong one-sided timing bias appeared in this sample." : `The session leaned ${t.label.replace("-leaning","")}. Watch whether this repeats on harder charts before changing offset.`}</p>
    </div>`;
  }


  function questsHtml() {
    const all = quests();
    const candidates = all.filter(q=>q.reward.endsWith(" est."));
    const practice = all.find(q=>!q.chart && q.reward!=="FLOOR");
    const floor = all.find(q=>q.reward==="FLOOR");
    return `${targetRowsHtml(candidates)}${practice ? `<aside class="practice-note"><h3>Practice idea</h3><p><strong>${safe(practice.title)}</strong><span>${safe(practice.sub)} · Based on this session’s level bands.</span></p></aside>` : ""}${floor ? `<aside class="pool-threshold-note"><h3>New 15 floor · ${num(after.new15Floor)}</h3><p>${safe(floor.title)}</p></aside>` : ""}`;
  }

  // Presentation-only sorting. Retain source indices so repeated plays of the
  // same chart still open their own details; never reorder the retained inputs.
  const scoreSorts = [
    {value: "recent", key: "time", direction: "descending", label: "Latest first"},
    {value: "oldest", key: "time", direction: "ascending", label: "Oldest first"},
    ...[
      ["song", "Song"], ["chart", "Chart"], ["achievement", "Achievement"],
      ["grade", "Grade"], ["rating", "Chart rating"], ["gain", "PB gain"],
      ["timing", "Fast / Slow"]
    ].flatMap(([key, label]) => ["ascending", "descending"].map(direction => ({
      value: direction === "descending" && ["achievement", "rating"].includes(key)
        ? key : `${key}-${direction === "ascending" ? "asc" : "desc"}`,
      key, direction, label: `${label} ${direction === "ascending" ? "↑" : "↓"}`
    })))
  ];
  const scoreColumns = [
    ["song", "Song"], ["chart", "Chart"], ["achievement", "Achievement"],
    ["grade", "Grade"], ["rating", "Rating"], ["gain", "PB gain"], ["timing", "Fast / Slow"]
  ];
  const scoreNumber = value => (typeof value === "number" || typeof value === "string") &&
    String(value).trim() !== "" && Number.isFinite(Number(value)) ? Number(value) : null;
  const scoreText = value => typeof value === "string" && value.trim() ? value.trim() : null;
  const scoreCollator = new Intl.Collator("en", {numeric: true, sensitivity: "base"});
  const scoreDifficulties = ["diff-basic", "diff-advanced", "diff-expert", "diff-master", "diff-remaster"];
  function scoreLevel(item) {
    const constant = scoreNumber(item.levelNum);
    const match = /^(\d+(?:\.\d+)?)(\+)?$/.exec(String(item.level ?? "").trim());
    // A displayed plus level is a band, not an estimated constant. Keep 9+
    // after every displayed 9 even when one chart has no retained constant.
    return match ? [Number(match[1]), match[2] ? 1 : 0, constant]
      : [constant == null ? null : Math.floor(constant), null, constant];
  }
  function scoreGain(item) {
    const current = scoreNumber(item.rate);
    const previous = item.changeType === "new" ? 0 : scoreNumber(item.previousRate);
    return current != null && previous != null ? current - previous : null;
  }
  function scoreSortValues(item, key) {
    switch (key) {
      case "song": return [scoreText(item.title)];
      case "chart": {
        const difficulty = scoreDifficulties.indexOf(diffClass(item.difficulty));
        return [difficulty < 0 ? null : difficulty, ...scoreLevel(item),
          scoreText(item.difficulty) ? (/^DX\s/i.test(item.difficulty) ? 1 : 0) : null];
      }
      case "achievement": return [scoreNumber(item.percent)];
      case "grade": return [gradeOrder.includes(item.grade) ? gradeOrder.length - gradeIndex(item.grade) : null];
      case "rating": return [scoreNumber(item.rate)];
      case "gain": return [scoreGain(item)];
      case "timing": return [scoreNumber(item.fast), scoreNumber(item.slow)];
      default: return [scoreNumber(item.timeAchieved)];
    }
  }
  function compareScoreValues(left, right, direction) {
    for (let index = 0; index < left.length; index++) {
      const a = left[index], b = right[index];
      // Missing values remain last even when the requested order is reversed.
      if (a == null || b == null) {
        if (a !== b) return a == null ? 1 : -1;
        continue;
      }
      const order = typeof a === "string" ? scoreCollator.compare(a, b) : a - b;
      if (order) return direction === "ascending" ? order : -order;
    }
    return 0;
  }
  function nextScoreSort(key, current) {
    const direction = current.key === key
      ? (current.direction === "ascending" ? "descending" : "ascending")
      : (["song", "chart", "timing"].includes(key) ? "ascending" : "descending");
    return scoreSorts.find(sort => sort.key === key && sort.direction === direction);
  }
  function scoreHeading(key, label) {
    const next = nextScoreSort(key, scoreSorts[0]);
    return `<th scope="col"${key === "gain" ? ' id="pb-gain-heading" hidden' : ""}><button type="button" class="score-sort-button" data-score-sort="${key}" aria-label="Sort by ${label}, ${next.direction}"><span>${label}</span><span class="score-sort-indicator" aria-hidden="true">↕</span></button></th>`;
  }
  function sessionRows(scope = "plays", sort = "recent") {
    const source = scope === "pbs" ? changedPBs : sessionScores;
    const selected = scoreSorts.find(item => item.value === sort) || scoreSorts[0];
    const list = source.map((item, index) => ({item, index, values: scoreSortValues(item, selected.key)}))
      .sort((a,b) => compareScoreValues(a.values, b.values, selected.direction) || a.index - b.index);
    if (!list.length) return `<tr class="empty-score-row"><td colspan="${scope === "pbs" ? 7 : 6}">${scope==="pbs"?"No score changes detected.":"No session plays retained."}</td></tr>`;
    return list.map(({item: x, index})=>`<tr data-search="${safe(`${x.title} ${x.artist} ${x.difficulty} ${x.grade} ${x.level}`.toLowerCase())}" data-difficulty="${diffClass(x.difficulty)}">
      <td><button type="button" class="song-cell chart-link" data-detail-source="${scope}" data-detail-index="${index}" aria-label="Score details: ${safe(x.title)}, ${safe(x.difficulty)} ${safe(x.level)}">${jacketHtml(x)}<span><span class="song-name">${safe(x.title || "Untitled chart")}</span><span class="song-artist">${safe(x.artist || "Artist unavailable")}</span></span></button></td>
      <td>${chartBadge(x)}</td><td data-label="Achievement" class="mono">${presentPct(scoreNumber(x.percent))}${scope==="pbs"?`<small class="previous-score">${x.changeType==="new"?"First recorded PB":`from ${presentPct(scoreNumber(x.previousPercent))}`}</small>`:""}</td><td data-label="Grade">${gradeHtml(x.grade)}</td>
      <td data-label="Rating" class="mono">${presentNum(scoreNumber(x.rate))}${scope==="pbs" && x.previousRate!=null?`<small class="previous-score">from ${presentNum(scoreNumber(x.previousRate))}</small>`:""}</td><td data-label="PB gain" ${scope==="plays"?"hidden":""} class="mono ${scoreGain(x)<0?"negative":"positive"}">${scoreGain(x) == null ? "—" : signed(scoreGain(x))}</td><td data-label="Fast / Slow" class="mono">${presentNum(scoreNumber(x.fast))} / ${presentNum(scoreNumber(x.slow))}</td>
    </tr>`).join("");
  }


  function poolItems(list, type, snapshot = "after") {
    if (!Array.isArray(list) || !list.length) return `<p class="mini-empty">No ${type === "new" ? "current-version" : "legacy"} scores are counted in this snapshot.</p>`;
    return [...list].sort((a,b)=>rate(b)-rate(a)||Number(b.percent)-Number(a.percent)||String(a.title).localeCompare(String(b.title))).map((x,i)=>`<button type="button" class="pool-item" data-detail-source="${snapshot}-${type}" data-detail-index="${list.indexOf(x)}" aria-label="Score details: ${safe(x.title)}, ${safe(x.difficulty)} ${safe(x.level)}" data-search="${safe(`${x.title} ${x.artist} ${x.difficulty} ${x.level} ${x.grade}`.toLowerCase())}">
      <span class="rank-number">${i+1}</span>${jacketHtml(x)}<span class="pool-name"><span class="pool-title">${safe(x.title)}</span>${chartBadge(x)}<span class="pool-meta">${presentPct(x.percent)} ${gradeHtml(x.grade)}</span></span><span class="pool-rate">${presentNum(x.rate)}<small>RT</small></span>
    </button>`).join("");
  }


  function overviewScoresHtml() {
    const moments = [...changedPBs].sort((a,b)=>gain(b)-gain(a)||rate(b)-rate(a)).slice(0,4);
    if (!moments.length) return `<p class="mini-empty">No new PBs this time.</p>`;
    return `<div class="score-list">${moments.map(x=>`<button type="button" class="score-row" data-detail-source="pbs" data-detail-index="${changedPBs.indexOf(x)}" aria-label="View ${safe(x.title)} score details">
      ${jacketHtml(x)}<span class="score-info"><strong>${safe(x.title)}</strong>${chartBadge(x)}<span class="score-achievement">${pct(x.percent)} ${gradeHtml(x.grade)}</span></span><span class="score-gain ${gain(x)<0?"negative":""}">${signed(gain(x))}<small>chart gain</small></span>
    </button>`).join("")}</div>`;
  }

  function poolSummaryHtml() {
    const rows = [{key:"old35Rating",name:"Old 35",kind:"old",pool:"old35",limit:35},{key:"new15Rating",name:"New 15",kind:"new",pool:"new15",limit:15},{key:"reconstructedRating",name:"Total",kind:"total"},{key:"naiveRating",name:"Kama Naive",kind:"naive"}];
    const gap = Math.abs(Number(after.naiveRating||0)-Number(after.reconstructedRating||0));
    return `<div class="comparison-wrap" role="region" aria-label="Rating before and after" tabindex="0"><table class="comparison-table"><thead><tr><th scope="col">Rating</th><th scope="col">Before</th><th scope="col">Now</th><th scope="col">Change</th></tr></thead><tbody>${rows.map(r=>`<tr class="${r.kind}"><th scope="row">${r.name}</th>${[before,after].map(snapshot=>`<td>${num(snapshot[r.key])}${r.pool?`<small class="pool-occupancy">${r.pool==="new15"?snapshot.newSlotsFilled??(snapshot.new15||[]).length:(snapshot[r.pool]||[]).length}/${r.limit} counted</small>`:""}</td>`).join("")}<td class="${Number(delta[r.key])<0?"negative":""}">${signed(delta[r.key])}</td></tr>`).join("")}</tbody></table></div>
    <div class="pool-floors"><p><strong>Old 35 floor</strong><span>${num(before.old35Floor)} → ${num(after.old35Floor)}</span></p><p><strong>New 15 floor</strong><span>${num(before.new15Floor)} → ${num(after.new15Floor)}${Number(after.newSlotsFilled||0)<15?" · Open slot":""}</span></p></div>
    <p class="pool-advice">Use these floors to judge whether a new chart is likely to count before spending a credit grinding it.</p>
    <dl class="account-coverage"><div><dt>Recorded PBs</dt><dd>${num(before.pbCount)} → ${num(after.pbCount)}</dd></div><div><dt>Current-version charts played</dt><dd>${num(before.newPoolPlayed)} → ${num(after.newPoolPlayed)}</dd></div></dl>
    <div class="model-note"><h3>Rating model · ${num(gap)} point Naive gap</h3><p>${gap<=20?"Your NaiveRating now closely mirrors the reconstructed B35/N15 total.":"Your unrestricted Best 50 still differs materially from the version-split rating model."}</p><p>Reconstructed rating counts Old 35 and New 15 separately. Kama Naive uses an unrestricted Best 50. ${safe(data.ratingVersionAssumption || "Configured-version Old 35 + New 15")}.</p></div>`;
  }


  function targetRowsHtml(candidates) {
    return `<div class="target-list">${candidates.map(q=>`<button type="button" class="target-row" data-detail-source="targets" data-detail-index="${(after.newPool || []).findIndex(x=>x.chartID===q.chart.chartID)}" aria-label="Target details: ${safe(q.title)}">${jacketHtml(q.chart)}<span><strong>${safe(q.title)}</strong>${chartBadge(q.chart)}<span class="target-progress">PB ${safe(q.sub)} ${gradeHtml("S")}</span></span><span class="target-estimate">${safe(q.reward)}</span></button>`).join("") || `<p class="mini-empty">No positive-gain S-threshold targets in this snapshot.</p>`}</div>${candidates.length ? `<p class="target-explanation">Potential gain at S, after the New 15 floor.</p>` : ""}`;
  }

  function overviewTargetsHtml() {
    return targetRowsHtml(quests().filter(q=>q.reward.endsWith(" est.")));
  }

  function overviewView() {
    return `<section id="overview-view" class="view active" data-view="overview" role="tabpanel" aria-labelledby="tab-overview">
      <div class="overview-lead"><section class="overview-scores"><div class="section-heading"><h2>Session highlights</h2><button type="button" class="text-action" data-open-view="session">All scores</button></div><p class="section-caption">Biggest PB gains, before counted-pool replacements.</p>${overviewScoresHtml()}</section>
        <section class="overview-targets"><div class="section-heading"><h2>Play next</h2><button type="button" class="text-action" data-open-view="targets">All targets</button></div>${overviewTargetsHtml()}<button type="button" class="analysis-link" data-open-view="targets"><span><strong>Find your practice focus</strong><small>Targets & session level bands</small></span><span aria-hidden="true">→</span></button></section></div>
    </section>`;
  }

  function sessionView() {
    const grades = gradeCounts();
    const total = grades.reduce((sum,[,count])=>sum+count,0);
    return `<section id="session-view" class="view" data-view="session" data-score-scope="plays"><header class="view-heading"><h1>Session scores</h1><p class="session-record-counts">${sessionScores.length} plays · ${changedPBs.length} PB changes<br>${num(session.newPBCount)} first PBs · ${num(session.improvedPBCount)} existing PBs changed</p></header>
      <section class="grade-section"><div class="section-heading"><h2>Grade distribution</h2><span class="section-caption">Highest to lowest · ${total} ${sessionScores.length?"plays":"PB records"}</span></div><div class="grade-distribution">${grades.map(([grade,count])=>`<div class="grade-count">${gradeHtml(grade)}<strong>${count}<small>${count===1?"play":"plays"}</small></strong><span class="grade-count-bar" style="--fill:${total?count/total*100:0}%"></span></div>`).join("")||`<p class="mini-empty">No session grades available.</p>`}</div></section>
      <section class="score-detail-section"><div class="score-controls"><label>Show<select id="score-scope"><option value="plays">All plays (${sessionScores.length})</option><option value="pbs">PB changes (${changedPBs.length})</option></select></label><label>Sort<select id="score-sort">${scoreSorts.map(sort => `<option value="${sort.value}"${sort.key === "gain" ? " hidden disabled" : ""}>${sort.label}</option>`).join("")}</select></label><label>Chart type<select id="score-difficulty"><option value="">All difficulties</option><option value="diff-basic">Basic</option><option value="diff-advanced">Advanced</option><option value="diff-expert">Expert</option><option value="diff-master">Master</option><option value="diff-remaster">Re:Master</option></select></label><label class="song-search">Search<input id="session-search" class="search-box" type="search" placeholder="Song or level…" /></label></div><p id="score-count" class="section-caption" role="status"></p>
        <p id="score-sort-help" class="section-caption">Chart sorts by difficulty, level, then format. Fast / Slow sorts by fast, then slow. Missing values stay last.</p><div class="session-table-wrap"><table class="session-table" aria-label="Session scores" aria-describedby="score-sort-help"><thead><tr>${scoreColumns.map(([key, label]) => scoreHeading(key, label)).join("")}</tr></thead><tbody id="session-rows">${sessionRows()}</tbody></table></div><p class="section-subtitle">PB changes compares each chart with its previous best. Chart gains can be larger than the net gain after pool replacements.</p></section>
      <section class="detail-timing"><div class="section-heading"><h2>Session timing</h2></div>${timingHtml()}</section>
    </section>`;
  }

  function poolsView() {
    const interpretation = story();
    return `<section id="pools-view" class="view" data-view="pools"><header class="view-heading"><h1>Rating breakdown</h1><p>Before and after, followed by every counted score.</p></header>
      <section class="rating-explanation"><div class="session-interpretation"><h2>${safe(interpretation.title)}</h2><p>${safe(interpretation.copy)}</p><p>New 15 version: ${safe((data.currentNewDisplayVersions || []).join(", ") || "Not specified")}</p></div><div>${poolSummaryHtml()}</div></section>
      <section class="counted-pools"><div class="section-heading"><h2>Counted scores</h2></div><div class="pool-controls"><label>Snapshot<select id="pool-snapshot"><option value="after">After session</option><option value="before">Before session</option></select></label><label>Search<input id="pool-search" class="search-box" type="search" placeholder="Song, grade or level…" aria-label="Filter rating pools" /></label></div><p id="pool-count" class="section-caption" role="status"></p><div class="pool-grid">
        <section aria-labelledby="old-pool-title"><header class="section-header"><div><h3 id="old-pool-title" class="section-title">Old 35</h3><p id="old-pool-summary" class="section-subtitle"></p></div></header><div id="old-pool" class="pool-list"></div></section>
        <section aria-labelledby="new-pool-title"><header class="section-header"><div><h3 id="new-pool-title" class="section-title">New 15</h3><p id="new-pool-summary" class="section-subtitle"></p></div></header><div id="new-pool" class="pool-list"></div></section>
      </div><p id="pool-empty" class="mini-empty" hidden>No counted charts match this search.</p></section></section>`;
  }


  function targetsView() {
    return `<section id="targets-view" class="view" data-view="targets"><header class="view-heading"><h1>Targets & practice</h1><p>Pick a rating target or a practice goal.</p></header>
      <div class="practice-layout"><section class="target-opportunities"><h2 class="section-title">Next targets</h2>${questsHtml()}</section><section class="practice-profile"><h2 class="section-title">Difficulty profile</h2><p class="section-subtitle">Retained plays across chart types and versions.</p>${bandsHtml()}</section></div></section>`;
  }

  function toolbarHtml() {
    return `<nav class="toolbar" aria-label="Report views"><a class="report-brand" href="#overview-view" data-open-view="overview" aria-label="maimai report overview"><span class="brand-word">mai<span>mai</span><b>DX</b></span></a><div class="tabs" role="tablist" aria-label="Report sections">
      <button id="tab-overview" class="tab active" role="tab" aria-selected="true" aria-controls="overview-view" data-target="overview"><span>Scorecard</span></button>
      <button id="tab-session" class="tab" role="tab" aria-selected="false" aria-controls="session-view" tabindex="-1" data-target="session"><span>Scores</span></button>
      <button id="tab-pools" class="tab" role="tab" aria-selected="false" aria-controls="pools-view" tabindex="-1" data-target="pools"><span>Rating pools</span></button>
      <button id="tab-targets" class="tab" role="tab" aria-selected="false" aria-controls="targets-view" tabindex="-1" data-target="targets"><span>Targets</span></button>
    </div>${download.href ? `<a id="download-b50" class="action-button" href="${safe(download.href)}" download="${safe(download.filename || "maimai-b50.webp")}">Download B50</a>` : download.unavailable ? `<span id="historical-b50-unavailable" class="action-button" aria-disabled="true">${safe(download.unavailableLabel || "B50 unavailable")}</span>` : '<button id="print-report" class="action-button">Print / Save PDF</button>'}</nav>`;
  }


  function footerHtml() {
    return `<footer class="footer"><span>maimai DX · Independent / unofficial companion</span><span>Private report · on-demand sync</span></footer>`;
  }

  app.innerHTML = `<div class="report">${toolbarHtml()}${heroHtml()}${overviewView()}${sessionView()}${poolsView()}${targetsView()}${footerHtml()}</div>`;


  function showView(target, moveFocus = false) {
    const selected = document.querySelector(`.tab[data-target="${target}"]`);
    if (!selected) return;
    document.querySelectorAll(".tab").forEach((button) => {
      const active = button === selected;
      button.classList.toggle("active", active);
      button.setAttribute("aria-selected", String(active));
      button.tabIndex = active ? 0 : -1;
    });
    document.querySelectorAll(".view").forEach((view) => {
      const active = view.dataset.view === target;
      view.classList.toggle("active", active);
      view.hidden = !active;
    });
    document.querySelector(".report").dataset.currentView = target;
    if (moveFocus) selected.focus();
    document.querySelector(".toolbar").scrollIntoView({block:"start",behavior:"instant"});
  }
  document.querySelectorAll(".view").forEach((view) => {
    view.setAttribute("role", "tabpanel");
    view.setAttribute("aria-labelledby", `tab-${view.dataset.view}`);
    view.hidden = !view.classList.contains("active");
  });
  document.querySelectorAll(".tab").forEach((button) => {
    button.addEventListener("click", () => showView(button.dataset.target));
    button.addEventListener("keydown", (event) => {
      if (event.altKey || event.ctrlKey || event.metaKey) return;
      const tabs = [...document.querySelectorAll(".tab")];
      const index = tabs.indexOf(button);
      const step = event.key === "ArrowRight" ? 1 : event.key === "ArrowLeft" ? -1 : 0;
      if (!step && event.key !== "Home" && event.key !== "End") return;
      event.preventDefault();
      const next = event.key === "Home" ? tabs[0] : event.key === "End" ? tabs[tabs.length-1] : tabs[(index+step+tabs.length)%tabs.length];
      showView(next.dataset.target, true);
    });
  });
  document.querySelectorAll("[data-open-view]").forEach((button) => {
    button.addEventListener("click", (event) => {
      event.preventDefault();
      const target = button.dataset.openView;
      const input = document.getElementById(target === "session" ? "session-search" : "pool-search");
      if (target === "session") {
        document.getElementById("score-scope").value = button.dataset.song ? "pbs" : "plays";
        document.getElementById("score-difficulty").value = "";
        document.getElementById("score-sort").value = "recent";
        updateScores();
      }
      if (input) { input.value = button.dataset.song || ""; input.dispatchEvent(new Event("input")); }
      showView(target, true);
    });
  });
  document.getElementById("session-search")?.setAttribute("aria-label", "Filter session scores");
  document.getElementById("pool-search")?.setAttribute("aria-label", "Filter rating pools");
  document.getElementById("print-report")?.addEventListener("click", () => window.print());

  function filterScores() {
    const query = document.getElementById("session-search").value.trim().toLowerCase();
    const difficulty = document.getElementById("score-difficulty").value;
    const rows = [...document.querySelectorAll("#session-rows tr[data-search]")];
    rows.forEach(row=>{row.hidden = !!((query && !query.split(/\s+/).every(token=>row.dataset.search.includes(token))) || (difficulty && row.dataset.difficulty!==difficulty));});
    document.getElementById("score-count").textContent = `${rows.filter(x=>!x.hidden).length} of ${rows.length} ${document.getElementById("score-scope").value === "pbs"?"PB changes":"plays"}`;
  }
  function updateScores() {
    const scope = document.getElementById("score-scope").value;
    const select = document.getElementById("score-sort");
    let current = scoreSorts.find(sort => sort.value === select.value) || scoreSorts[0];
    if (scope !== "pbs" && current.key === "gain") current = scoreSorts[0];
    select.value = current.value;
    scoreSorts.forEach(sort => {
      const option = select.querySelector(`option[value="${sort.value}"]`);
      option.disabled = option.hidden = sort.key === "gain" && scope !== "pbs";
    });
    document.querySelectorAll("[data-score-sort]").forEach(button => {
      const key = button.dataset.scoreSort;
      const active = current.key === key;
      if (active) button.closest("th").setAttribute("aria-sort", current.direction);
      else button.closest("th").removeAttribute("aria-sort");
      const next = nextScoreSort(key, current);
      const label = scoreColumns.find(([column]) => column === key)[1];
      button.setAttribute("aria-label", `Sort by ${label}, ${next.direction}`);
      button.querySelector(".score-sort-indicator").textContent = active
        ? (current.direction === "ascending" ? "↑" : "↓") : "↕";
    });
    document.getElementById("session-view").dataset.scoreScope = scope;
    document.getElementById("session-rows").innerHTML = sessionRows(scope, current.value);
    document.getElementById("pb-gain-heading").hidden = scope !== "pbs";
    filterScores();
  }
  document.querySelectorAll("[data-score-sort]").forEach(button => {
    button.addEventListener("click", () => {
      const select = document.getElementById("score-sort");
      const current = scoreSorts.find(sort => sort.value === select.value) || scoreSorts[0];
      select.value = nextScoreSort(button.dataset.scoreSort, current).value;
      updateScores();
    });
  });
  ["score-scope","score-sort"].forEach(id=>document.getElementById(id).addEventListener("change",updateScores));
  document.getElementById("session-search").addEventListener("input",filterScores);
  document.getElementById("score-difficulty").addEventListener("change",filterScores);
  filterScores();
  function filterPools() {
    const query = document.getElementById("pool-search").value.trim().toLowerCase();
    const rows = [...document.querySelectorAll(".pool-list .pool-item")];
    rows.forEach(row=>{row.hidden=!!(query && !query.split(/\s+/).every(token=>row.dataset.search.includes(token)));});
    const shown = rows.filter(row=>!row.hidden).length;
    const snapshot = document.getElementById("pool-snapshot").value;
    document.getElementById("pool-count").textContent = `${shown} of ${rows.length} counted charts · ${snapshot==="before"?"Before":"After"} session · Highest rating first`;
    document.getElementById("pool-empty").hidden = !rows.length || shown !== 0;
  }
  function updatePools() {
    const snapshot = document.getElementById("pool-snapshot").value;
    const model = snapshot === "before" ? before : after;
    for (const [type, key, limit] of [["old","old35",35],["new","new15",15]]) {
      document.getElementById(`${type}-pool`).innerHTML = poolItems(model[key],type,snapshot);
      document.getElementById(`${type}-pool-summary`).textContent = `${num(model[key+"Rating"])} rating · ${(model[key]||[]).length}/${limit} counted · floor ${num(model[key+"Floor"])}`;
    }
    filterPools();
  }
  document.getElementById("pool-snapshot").addEventListener("change",updatePools);
  document.getElementById("pool-search").addEventListener("input",filterPools);
  updatePools();

  // Detail records are references to retained inputs; no score is recalculated here.
  const detailSources = {
    plays: sessionScores, pbs: changedPBs, targets: after.newPool || [],
    "before-old": before.old35 || [], "before-new": before.new15 || [],
    "after-old": after.old35 || [], "after-new": after.new15 || []
  };
  const chartDialog = document.createElement("dialog");
  chartDialog.className = "chart-dialog";
  chartDialog.setAttribute("aria-labelledby", "chart-detail-title");
  document.body.appendChild(chartDialog);
  let detailOpener;

  function recordedTime(value) {
    if (!Number.isFinite(value)) return "Time not retained";
    return new Intl.DateTimeFormat("en-US", {timeZone:player.timezone||"UTC",dateStyle:"medium",timeStyle:"short"}).format(new Date(value));
  }
  function openChartDetails(button) {
    const source = button.dataset.detailSource;
    const item = detailSources[source]?.[Number(button.dataset.detailIndex)];
    if (!item) return;
    const context = ({plays:"Session play",pbs:"Personal-best change",targets:"Target chart","before-old":"Old 35 · Before session","before-new":"New 15 · Before session","after-old":"Old 35 · After session","after-new":"New 15 · After session"})[source];
    const target = source === "targets" ? quests().find(q=>q.chart?.chartID===item.chartID && q.reward.endsWith(" est.")) : null;
    const field = (label,value) => `<div><dt>${label}</dt><dd>${value}</dd></div>`;
    chartDialog.innerHTML = `<header class="chart-dialog-header"><span>${context}</span><button type="button" class="detail-close" aria-label="Close score details">×</button></header><div class="chart-dialog-body">
      <div class="detail-song">${jacketHtml(item)}<div><h2 id="chart-detail-title">${safe(item.title || "Untitled chart")}</h2><p>${safe(item.artist || "Artist unavailable")}</p>${chartBadge(item)}</div></div>
      <div class="detail-result"><div><span>Achievement</span><strong>${presentPct(item.percent)}</strong>${gradeHtml(item.grade)}</div><div><span>Chart rating</span><strong>${presentNum(item.rate)}<small>RT</small></strong></div></div>
      ${source==="pbs"?`<section class="detail-section"><h3>${item.changeType==="new"?"First recorded PB":"PB comparison"}</h3><table class="detail-comparison"><thead><tr><th scope="col">Metric</th><th scope="col">Previous</th><th scope="col">Now</th></tr></thead><tbody><tr><th scope="row">Achievement</th><td>${presentPct(item.previousPercent)}</td><td>${presentPct(item.percent)}</td></tr><tr><th scope="row">Chart rating</th><td>${presentNum(item.previousRate)}</td><td>${presentNum(item.rate)}</td></tr></tbody></table><p class="detail-note"><strong class="${gain(item)<0?"negative":"positive"}">${signed(gain(item))} chart gain.</strong> This compares PB chart ratings; the session’s net gain also accounts for counted-pool replacements.</p></section>`:""}
      ${target?`<section class="detail-section target-detail"><h3>Next rating opportunity</h3><p>${safe(target.sub)} · ${safe(target.reward)}</p><p class="detail-note">${safe(target.copy)} This estimate considers the New 15 floor.</p></section>`:""}
      <section class="detail-section"><h3>Recorded score details</h3><dl class="detail-facts">${field("Lamp",safe(item.lamp || "—"))}${field("Chart constant",presentNum(item.levelNum))}${field("Fast",presentNum(item.fast))}${field("Slow",presentNum(item.slow))}</dl></section>
      <section class="detail-section"><h3>Judgements</h3><dl class="judgement-grid">${[["Critical perfect","pcrit"],["Perfect","perfect"],["Great","great"],["Good","good"],["Miss","miss"]].map(([label,key])=>field(label,presentNum(item[key]))).join("")}</dl></section>
      <p class="detail-note">${safe(recordedTime(item.timeAchieved))} · ${safe(player.timezone || "UTC")}<br>${safe(item.displayVersion || "Version not retained")}</p><p class="detail-note">A dash means that field was not retained.</p>
    </div>`;
    detailOpener = button;
    chartDialog.showModal();
    document.body.classList.add("chart-dialog-open");
    chartDialog.querySelector(".detail-close").focus();
  }
  app.addEventListener("click", event=>{
    const button = event.target.closest("button[data-detail-source]");
    if (button) openChartDetails(button);
  });
  chartDialog.addEventListener("click", event=>{
    if (event.target.closest(".detail-close")) chartDialog.close();
    if (event.target === chartDialog) {
      const box = chartDialog.getBoundingClientRect();
      if (event.clientX<box.left || event.clientX>box.right || event.clientY<box.top || event.clientY>box.bottom) chartDialog.close();
    }
  });
  chartDialog.addEventListener("close", ()=>{
    document.body.classList.remove("chart-dialog-open");
    if (detailOpener?.isConnected) detailOpener.focus();
  });
  chartDialog.addEventListener("keydown", event=>{
    if (event.key !== "Tab") return;
    const controls = [...chartDialog.querySelectorAll('button, a[href], input, select, textarea, [tabindex]:not([tabindex="-1"])')].filter(el=>!el.disabled && el.getClientRects().length);
    const first = controls[0], last = controls[controls.length-1];
    if ((event.shiftKey && document.activeElement === first) || (!event.shiftKey && document.activeElement === last)) {
      event.preventDefault();
      (event.shiftKey ? last : first)?.focus();
    }
  });

})();
