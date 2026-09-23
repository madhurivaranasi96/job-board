/* Rolefit static board — GitHub Pages. Tracking stays in localStorage. */
const STORE_KEY = "rolefit-board-v1";
const VISA_LABELS = {
  available: "Sponsorship Available",
  likely: "Sponsorship Likely",
  unknown: "Visa sponsorship: Unknown",
  none: "No Sponsorship",
  auth_required: "Existing Work Authorization Required",
  not_applicable: "Not Applicable / Remote",
};
const STATUSES = [
  ["saved", "Saved"],
  ["preparing", "Preparing"],
  ["applied", "Applied"],
  ["recruiter_contact", "Recruiter Contact"],
  ["interview", "Interview"],
  ["technical_interview", "Technical Interview"],
  ["final_interview", "Final Interview"],
  ["offer", "Offer"],
  ["rejected", "Rejected"],
  ["withdrawn", "Withdrawn"],
  ["skipped", "Skipped"],
];
const DEFAULT_PROFILE = {
  name: "Madhuri Varanasi",
  headline: "Senior Software Engineer · C# .NET · Angular · Agentic AI",
  yearsExperience: 7,
  location: "Hyderabad, India",
  skills: ["C#", ".NET", "ASP.NET", "Web API", "REST", "Angular", "AngularJS", "JavaScript", "TypeScript", "Agentic AI", "LLM"],
  preferredTitles: ["Senior Software Engineer", "Software Engineer", "Full Stack Engineer", ".NET Developer", "C# Developer", "Backend Engineer", "Frontend Engineer", "Angular Developer", "AI Engineer"],
  preferredTechnologies: ["C#", ".NET", "ASP.NET", "Web API", "Angular", "TypeScript", "JavaScript", "REST", "SQL", "Azure", "AWS", "AI", "LLM"],
  preferredIndustries: ["Banking", "Financial Services", "ATM / Payments", "FinTech", "Enterprise Software", "Technology"],
  preferredCountries: ["United States", "Canada", "United Kingdom", "Ireland", "Germany", "Netherlands", "India", "Australia", "Singapore"],
  preferredRegions: ["Worldwide", "Remote Anywhere", "Europe", "North America"],
  remotePreference: "any",
  visaPreference: "sponsorship",
  relocation: true,
  minExperience: 4,
  salaryMin: null,
  salaryCurrency: "",
  domainKeywords: ["banking", "atm", "payments", "fintech", "financial", "ndc", "enterprise", "production support"],
};

const state = {
  jobs: [],
  updatedAt: null,
  profile: { ...DEFAULT_PROFILE },
  applications: {},
  saved: [],
  skipped: [],
  search: "",
  sort: "match",
  filters: {
    country: "", region: "", city: "", workArrangement: "", visa: "",
    experience: "", title: "", technology: "", industry: "", jobType: "",
    posted: "", salaryCurrency: "", salaryMin: "", salaryMax: "", salaryDisclosedOnly: false,
  },
  selected: null,
};

function loadStore() {
  try {
    const raw = JSON.parse(localStorage.getItem(STORE_KEY) || "{}");
    if (raw.profile) state.profile = { ...DEFAULT_PROFILE, ...raw.profile };
    if (raw.applications) state.applications = raw.applications;
    if (raw.saved) state.saved = raw.saved;
    if (raw.skipped) state.skipped = raw.skipped;
  } catch { /* ignore */ }
}
function saveStore() {
  localStorage.setItem(STORE_KEY, JSON.stringify({
    profile: state.profile,
    applications: state.applications,
    saved: state.saved,
    skipped: state.skipped,
  }));
}

function escapeHtml(s) {
  const map = {
    "&": String.fromCharCode(38) + "amp;",
    "<": String.fromCharCode(38) + "lt;",
    ">": String.fromCharCode(38) + "gt;",
    '"': String.fromCharCode(38) + "quot;",
    "'": "&#39;",
  };
  return String(s ?? "").replace(/[&<>"']/g, (c) => map[c] || c);
}
function postedAgo(iso) {
  if (!iso) return "Date unknown";
  const t = new Date(iso).getTime();
  if (Number.isNaN(t)) return "Date unknown";
  const d = Math.round((Date.now() - t) / 86400000);
  if (d <= 0) return "today";
  if (d === 1) return "1 day ago";
  return `${d} days ago`;
}
function loc(job) {
  if (job.city && job.country) return `${job.city}, ${job.country}`;
  return job.country || job.location || "Unknown";
}
function arrange(a) {
  return ({ remote: "Remote", hybrid: "Hybrid", onsite: "On-site" }[a] || "Unknown");
}

function scoreJob(job, profile) {
  const hay = `${job.title} ${job.company} ${job.location} ${job.description} ${(job.technologies || []).join(" ")}`.toLowerCase();
  const reasons = [];
  const missing = [];
  const concerns = [];
  let score = 0;
  const core = ["C#", ".NET", "Angular", "JavaScript", "TypeScript", "Web API", "REST", "ASP.NET"];
  const tech = new Set(job.technologies || []);
  let skillPts = 0;
  for (const s of core) {
    const hit = [...tech].some((t) => t.toLowerCase() === s.toLowerCase()) || hay.includes(s.toLowerCase()) ||
      (s === "C#" && /c#|csharp/.test(hay)) || (s === ".NET" && /\.net|dotnet/.test(hay));
    if (hit) { skillPts += 5; reasons.push(s); }
  }
  score += Math.min(40, skillPts);
  const extras = ["React", "Python", "Java", "Go", "Azure", "AWS"];
  const have = new Set((profile.skills || []).map((s) => s.toLowerCase()));
  for (const t of tech) {
    if (extras.includes(t) && !have.has(t.toLowerCase()) && !missing.includes(t)) missing.push(t);
  }
  const title = (job.title || "").toLowerCase();
  const prefHit = (profile.preferredTitles || []).find((p) => title.includes(p.toLowerCase().split(" ")[0]) && title.includes("engineer") || title.includes(p.toLowerCase()));
  if (prefHit) { score += /senior|sr/.test(title) ? 20 : 16; reasons.push(prefHit); }
  else if (/software (engineer|developer)|full[- ]stack|backend|frontend/.test(title)) { score += 10; reasons.push("Adjacent software engineering title"); }
  else concerns.push("Title is outside the usual preferred set");
  const years = profile.yearsExperience;
  const need = job.experienceYearsMin;
  if (need == null) score += 10;
  else if (years >= need) { score += 15; reasons.push(`${years}+ years experience`); }
  else { score += 4; concerns.push(`Role asks for ${need}+ years`); }
  let domain = 0;
  for (const kw of profile.domainKeywords || []) if (hay.includes(kw.toLowerCase())) { domain += 4; reasons.push(kw); }
  score += Math.min(10, domain);
  if (job.workArrangement === "remote") { score += 10; reasons.push("Remote eligible"); }
  else if ((profile.preferredCountries || []).some((c) => (job.country || "").toLowerCase().includes(c.toLowerCase()))) score += 8;
  else if (job.countryCode === "IN") score += 8;
  else if (profile.relocation) score += 4;
  if (profile.visaPreference === "sponsorship") {
    if (job.visaStatus === "available") { score += 5; reasons.push("Visa sponsorship mentioned"); }
    else if (job.visaStatus === "likely" || job.visaStatus === "not_applicable") score += 3;
    else if (job.visaStatus === "unknown") score += 2;
    else concerns.push("Employer may not sponsor a work visa");
  }
  return {
    ...job,
    matchScore: Math.max(0, Math.min(100, Math.round(score))),
    matchReasons: [...new Set(reasons)].slice(0, 8),
    missingRequirements: missing.slice(0, 6),
    concerns: [...new Set(concerns)].slice(0, 5),
  };
}

function matchesSearch(job, q) {
  const parts = q.trim().toLowerCase().split(/\s+/).filter(Boolean);
  if (!parts.length) return true;
  const hay = [job.title, job.company, job.description, job.location, job.city, job.country, job.visaLabel, job.visaStatus, ...(job.technologies || []), ...(job.visaEvidence || [])].join(" ").toLowerCase();
  return parts.every((p) => hay.includes(p));
}
function regionMatch(job, region) {
  if (!region) return true;
  const remote = job.workArrangement === "remote";
  const map = {
    worldwide: true,
    "worldwide-remote": remote,
    "remote-usa": remote && (job.countryCode === "US" || job.countryCode === "REMOTE"),
    "remote-europe": remote && (job.region === "europe" || job.countryCode === "REMOTE"),
    "remote-uk": remote && job.countryCode === "GB",
    "remote-canada": remote && job.countryCode === "CA",
    "remote-apac": remote && (job.region === "asia-pacific" || job.countryCode === "REMOTE"),
    "remote-india": remote && job.countryCode === "IN",
    "remote-anywhere": remote,
    "north-america": job.region === "north-america",
    europe: job.region === "europe",
    "asia-pacific": job.region === "asia-pacific",
    "middle-east": job.region === "middle-east",
    "south-asia": job.region === "south-asia",
  };
  return map[region] ?? job.region === region;
}
function applyFilters(list) {
  const f = state.filters;
  return list.filter((job) => {
    if (job.status === "closed" || state.skipped.includes(job.id)) return false;
    if (!matchesSearch(job, state.search)) return false;
    if (f.country && f.country !== "REMOTE" && job.countryCode !== f.country && !(job.country || "").includes(f.country)) return false;
    if (f.country === "REMOTE" && job.workArrangement !== "remote") return false;
    if (!regionMatch(job, f.region)) return false;
    if (f.city && !(job.city || "").toLowerCase().includes(f.city.toLowerCase())) return false;
    if (f.workArrangement && job.workArrangement !== f.workArrangement) return false;
    if (f.visa && job.visaStatus !== f.visa) return false;
    if (f.technology && f.technology !== "Other") {
      const hay = `${(job.technologies || []).join(" ")} ${job.title} ${job.description}`.toLowerCase();
      if (!hay.includes(f.technology.toLowerCase()) && !(f.technology === "C#" && /c#|csharp/.test(hay)) && !(f.technology === ".NET" && /\.net|dotnet/.test(hay))) return false;
    }
    if (f.industry && f.industry !== "Other" && !(job.industry || "").toLowerCase().includes(f.industry.toLowerCase())) return false;
    if (f.jobType && job.jobType !== f.jobType) return false;
    if (f.title && f.title !== "Other" && !job.title.toLowerCase().includes(f.title.toLowerCase().split(" ")[0])) {
      const toks = f.title.toLowerCase().split(/\s+/);
      if (!toks.every((t) => t.length < 3 || job.title.toLowerCase().includes(t))) return false;
    }
    if (f.posted) {
      if (job.postedAt) {
        const diff = Date.now() - new Date(job.postedAt).getTime();
        if (diff > Number(f.posted) * 86400000) return false;
      }
    }
    if (f.salaryDisclosedOnly && (!job.salaryMin || job.salary === "Not specified")) return false;
    return true;
  });
}
function sortJobs(list) {
  const copy = [...list];
  const visaRank = { available: 5, likely: 4, not_applicable: 3, unknown: 2, auth_required: 1, none: 0 };
  copy.sort((a, b) => {
    if (state.sort === "newest") return (b.postedAt || "").localeCompare(a.postedAt || "");
    if (state.sort === "company") return a.company.localeCompare(b.company);
    if (state.sort === "salary") return (b.salaryMax || 0) - (a.salaryMax || 0);
    if (state.sort === "sponsorship") return (visaRank[b.visaStatus] || 0) - (visaRank[a.visaStatus] || 0);
    return (b.matchScore - a.matchScore) || (b.postedAt || "").localeCompare(a.postedAt || "");
  });
  return copy;
}

function route() {
  const h = (location.hash || "#/").replace(/^#/, "") || "/";
  return h.split("?")[0];
}

function scoredJobs() {
  return state.jobs.map((j) => scoreJob(j, state.profile));
}

function presetList(path, jobs) {
  if (path === "/visa") return jobs.filter((j) => j.visaStatus === "available" || j.visaStatus === "likely");
  if (path === "/remote") return jobs.filter((j) => j.workArrangement === "remote");
  if (path === "/matches") return jobs.filter((j) => j.matchScore >= 70);
  if (path === "/saved") return jobs.filter((j) => state.saved.includes(j.id));
  return jobs;
}

function selectOpts(id, label, value, options) {
  return `<label>${escapeHtml(label)}<select id="${id}">${options.map(([v, l]) => `<option value="${escapeHtml(v)}" ${v === value ? "selected" : ""}>${escapeHtml(l)}</option>`).join("")}</select></label>`;
}

function filterBar(jobs) {
  const countries = [["", "Any country"], ["REMOTE", "Remote / Worldwide"], ...[...new Set(jobs.map((j) => [j.countryCode, j.country]).filter((x) => x[0] && x[0] !== "REMOTE").map((x) => JSON.stringify(x)))].map((s) => JSON.parse(s))];
  const f = state.filters;
  return `<section class="filters">
    <div class="row two">
      <label>Search<input id="search" type="search" placeholder='e.g. ".NET Angular Germany sponsorship"' value="${escapeHtml(state.search)}" /></label>
      ${selectOpts("sort", "Sort", state.sort, [["match","Match"],["newest","Newest"],["sponsorship","Sponsorship"],["salary","Salary"],["company","Company"]])}
    </div>
    <div class="row four">
      ${selectOpts("country", "Country", f.country, countries)}
      ${selectOpts("region", "Region", f.region, [["","Any region"],["worldwide","Worldwide"],["worldwide-remote","Worldwide Remote"],["remote-usa","Remote USA"],["remote-europe","Remote Europe"],["remote-uk","Remote UK"],["remote-canada","Remote Canada"],["remote-apac","Remote Asia-Pacific"],["remote-india","Remote India"],["remote-anywhere","Remote Anywhere"],["north-america","North America"],["europe","Europe"],["asia-pacific","Asia-Pacific"]])}
      ${selectOpts("arrange", "Work arrangement", f.workArrangement, [["","Any"],["remote","Remote"],["hybrid","Hybrid"],["onsite","On-site"]])}
      ${selectOpts("visa", "Visa", f.visa, [["","Any"],["available","Sponsorship Available"],["likely","Sponsorship Likely"],["unknown","Unknown"],["none","No Sponsorship"],["auth_required","Existing Authorization Required"],["not_applicable","Not Applicable / Remote"]])}
      ${selectOpts("tech", "Technology", f.technology, [["","Any"],["C#","C#"],[".NET",".NET"],["ASP.NET","ASP.NET"],["Web API","Web API"],["Angular","Angular"],["JavaScript","JavaScript"],["TypeScript","TypeScript"],["REST","REST"],["SQL","SQL"],["Azure","Azure"],["AWS","AWS"],["AI","AI"],["LLM","LLM"]])}
      ${selectOpts("industry", "Industry", f.industry, [["","Any"],["Banking","Banking"],["Financial Services","Financial Services"],["ATM / Payments","ATM / Payments"],["FinTech","FinTech"],["Enterprise Software","Enterprise Software"],["Technology","Technology"]])}
      ${selectOpts("type", "Job type", f.jobType, [["","Any"],["full-time","Full-time"],["permanent","Permanent"],["contract","Contract"],["temporary","Temporary"]])}
      ${selectOpts("posted", "Posted", f.posted, [["","Any time"],["1","Today"],["3","Last 3 days"],["7","Last 7 days"],["14","Last 14 days"],["30","Last 30 days"]])}
    </div>
    <button class="btn btn-ghost" id="clear">Clear filters</button>
  </section>`;
}

function visaChip(status) {
  const cls = status === "available" ? "match" : status === "none" || status === "auth_required" ? "warn" : "visa";
  return `<span class="chip ${cls}">${escapeHtml(VISA_LABELS[status] || "Unknown")}</span>`;
}

function jobCard(job) {
  const saved = state.saved.includes(job.id);
  const st = state.applications[job.id]?.status;
  return `<article class="card" data-id="${job.id}">
    <div class="head">
      <div>
        <h3><button class="open" data-id="${job.id}" style="all:unset;cursor:pointer">${escapeHtml(job.title)}</button></h3>
        <p class="co">${escapeHtml(job.company)} · ${escapeHtml(loc(job))}</p>
      </div>
      <div class="score">${job.matchScore}%<small>Match</small></div>
    </div>
    <div class="chips">
      <span class="chip">${escapeHtml(arrange(job.workArrangement))}</span>
      ${visaChip(job.visaStatus)}
      ${job.experience ? `<span class="chip">${escapeHtml(job.experience)}</span>` : ""}
      ${st ? `<span class="chip visa">${escapeHtml((STATUSES.find((s) => s[0] === st) || [st, st])[1])}</span>` : ""}
    </div>
    <p class="co">${escapeHtml((job.technologies || []).slice(0, 8).join(" · "))}</p>
    <div class="reasons">${(job.matchReasons || []).slice(0, 5).map((r) => `<span>✓ ${escapeHtml(r)}</span>`).join("")}</div>
    ${(job.missingRequirements || []).length ? `<p class="missing">Missing: ${escapeHtml(job.missingRequirements.slice(0, 4).join(", "))}</p>` : ""}
    <div class="actions">
      <span class="meta">Posted ${escapeHtml(postedAgo(job.postedAt))}</span>
      <div>
        <button class="btn btn-ghost save" data-id="${job.id}">${saved ? "Saved" : "Save"}</button>
        <button class="btn btn-secondary open" data-id="${job.id}">Details</button>
        <a class="btn btn-primary" href="${escapeHtml(job.applyUrl)}" target="_blank" rel="noopener">Apply</a>
      </div>
    </div>
  </article>`;
}

function bindFilters() {
  const el = (id) => document.getElementById(id);
  // Search: keep the input in the DOM so focus is never lost while typing
  if (el("search")) {
    el("search").oninput = (e) => {
      state.search = e.target.value;
      debouncedRefreshJobList();
    };
  }
  if (el("sort")) el("sort").onchange = (e) => { state.sort = e.target.value; render(); };
  ["country","region","arrange","visa","tech","industry","type","posted"].forEach((id) => {
    const node = el(id);
    if (!node) return;
    const key = { arrange: "workArrangement", tech: "technology", type: "jobType" }[id] || id;
    node.onchange = (e) => { state.filters[key] = e.target.value; render(); };
  });
  const clear = el("clear");
  if (clear) clear.onclick = () => {
    state.search = "";
    state.sort = "match";
    Object.keys(state.filters).forEach((k) => { state.filters[k] = typeof state.filters[k] === "boolean" ? false : ""; });
    render();
  };
}
function debounce(fn, ms) {
  let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); };
}
const debouncedRefreshJobList = debounce(() => refreshJobList(), 120);

function dashboard(jobs) {
  const active = jobs.filter((j) => j.status !== "closed");
  const apps = Object.values(state.applications);
  const today = new Date().toISOString().slice(0, 10);
  const items = [
    ["Active jobs", active.length, "#/jobs"],
    ["High match", active.filter((j) => j.matchScore >= 70).length, "#/matches"],
    ["Sponsorship", active.filter((j) => j.visaStatus === "available" || j.visaStatus === "likely").length, "#/visa"],
    ["Remote", active.filter((j) => j.workArrangement === "remote").length, "#/remote"],
    ["Saved", state.saved.length, "#/saved"],
    ["Applied", apps.filter((a) => a.status === "applied" || (a.status || "").includes("interview") || a.status === "offer").length, "#/applications"],
    ["Added today", active.filter((j) => (j.postedAt || "").startsWith(today) || (j.firstDiscovered || "").startsWith(today)).length, ""],
    ["Closed", jobs.filter((j) => j.status === "closed").length, ""],
  ];
  const top = sortJobs(applyFilters(active)).slice(0, 5);
  return `<header>
      <p class="meta">Personal job search</p>
      <h1>${escapeHtml(state.profile.name.split(" ")[0])}, here is the board</h1>
      <p class="lede">Roles scored against your ${state.profile.yearsExperience}+ years in ${escapeHtml(state.profile.headline)}. Sponsorship is only marked when the posting says so.</p>
      ${state.updatedAt ? `<p class="meta">Feed updated ${escapeHtml(new Date(state.updatedAt).toUTCString())}</p>` : ""}
    </header>
    <div class="stats">${items.map(([l,v,href]) => href ? `<a class="stat" href="${href}"><span>${l}</span><b>${v}</b></a>` : `<div class="stat"><span>${l}</span><b>${v}</b></div>`).join("")}</div>
    <h2>Highest matches</h2>
    <div class="cards">${top.map(jobCard).join("") || empty("No roles yet")}</div>`;
}

function empty(msg) { return `<div class="empty"><h2>${msg}</h2><p class="lede">Try clearing filters or check back after the daily refresh.</p></div>`; }

function listPage(title, lede, path, jobs) {
  const list = sortJobs(applyFilters(presetList(path, jobs)));
  return `<header><h1>${title}</h1><p class="lede">${lede}</p>${state.updatedAt ? `<p class="meta">Feed updated ${escapeHtml(new Date(state.updatedAt).toUTCString())}</p>` : ""}</header>
    ${filterBar(jobs)}
    <p class="meta" id="job-count">${list.length} role${list.length === 1 ? "" : "s"}</p>
    <div class="cards" id="job-cards">${list.map(jobCard).join("") || empty("No matching roles")}</div>`;
}

/** Update only the job list (keeps search input focused while typing). */
function refreshJobList() {
  const path = route();
  if (!["/jobs", "/visa", "/remote", "/matches", "/saved"].includes(path)) {
    render();
    return;
  }
  const jobs = scoredJobs();
  const list = sortJobs(applyFilters(presetList(path, jobs)));
  const countEl = document.getElementById("job-count");
  const cardsEl = document.getElementById("job-cards");
  if (!countEl || !cardsEl) {
    render();
    return;
  }
  countEl.textContent = list.length + " role" + (list.length === 1 ? "" : "s");
  cardsEl.innerHTML = list.map(jobCard).join("") || empty("No matching roles");
  bindCards(cardsEl);
}

function applicationsPage(jobs) {
  const byId = Object.fromEntries(jobs.map((j) => [j.id, j]));
  const rows = Object.values(state.applications)
    .map((a) => ({ ...a, job: byId[a.jobId] }))
    .filter((a) => a.job)
    .sort((a, b) => (b.appliedAt || "").localeCompare(a.appliedAt || ""));
  if (!rows.length) return empty("No applications tracked yet");
  return `<header><h1>Applications</h1><p class="lede">Status is stored in this browser only.</p></header>
    <div class="cards">${rows.map((a) => {
      const job = a.job;
      return `<article class="card">
        <div class="head"><div><h3>${escapeHtml(job.title)}</h3><p class="co">${escapeHtml(job.company)}</p></div>
          <span class="chip visa">${escapeHtml((STATUSES.find((s) => s[0] === a.status) || [a.status, a.status])[1])}</span></div>
        <p class="meta">Applied ${escapeHtml(a.appliedAt || "—")} · ${escapeHtml(a.recruiter || "")}</p>
        <div class="actions"><button class="btn btn-secondary open" data-id="${job.id}">Open</button></div>
      </article>`;
    }).join("")}</div>`;
}

function profilePage() {
  const p = state.profile;
  return `<header><h1>Profile</h1><p class="lede">Used only for scoring. Nothing is uploaded.</p></header>
    <form id="profile-form" class="filters">
      <div class="row two">
        <label>Name<input name="name" value="${escapeHtml(p.name)}" /></label>
        <label>Headline<input name="headline" value="${escapeHtml(p.headline)}" /></label>
        <label>Years experience<input name="yearsExperience" type="number" min="0" value="${p.yearsExperience}" /></label>
        <label>Location<input name="location" value="${escapeHtml(p.location)}" /></label>
      </div>
      <label>Skills (comma-separated)<input name="skills" value="${escapeHtml((p.skills || []).join(", "))}" /></label>
      <label>Preferred titles<input name="preferredTitles" value="${escapeHtml((p.preferredTitles || []).join(", "))}" /></label>
      <label>Preferred technologies<input name="preferredTechnologies" value="${escapeHtml((p.preferredTechnologies || []).join(", "))}" /></label>
      <label>Preferred industries<input name="preferredIndustries" value="${escapeHtml((p.preferredIndustries || []).join(", "))}" /></label>
      <label>Preferred countries<input name="preferredCountries" value="${escapeHtml((p.preferredCountries || []).join(", "))}" /></label>
      <div class="row two">
        <label>Remote preference<select name="remotePreference">
          <option value="any" ${p.remotePreference==="any"?"selected":""}>Any</option>
          <option value="remote" ${p.remotePreference==="remote"?"selected":""}>Prefer remote</option>
          <option value="hybrid" ${p.remotePreference==="hybrid"?"selected":""}>Prefer hybrid</option>
        </select></label>
        <label>Visa preference<select name="visaPreference">
          <option value="sponsorship" ${p.visaPreference==="sponsorship"?"selected":""}>Prefer sponsorship</option>
          <option value="any" ${p.visaPreference==="any"?"selected":""}>Any</option>
        </select></label>
      </div>
      <label style="display:flex;align-items:center;gap:8px;"><input type="checkbox" name="relocation" ${p.relocation?"checked":""} /> Open to relocation</label>
      <div>
        <button class="btn btn-primary" type="submit">Save preferences</button>
        <button class="btn btn-ghost" type="button" id="reset-profile">Reset to resume defaults</button>
      </div>
    </form>`;
}

function openModal(job) {
  state.selected = job.id;
  const rec = state.applications[job.id] || {};
  const modal = document.getElementById("modal");
  modal.classList.remove("hidden");
  modal.innerHTML = `<div class="panel">
    <button class="close" aria-label="Close">×</button>
    <h2>${escapeHtml(job.title)}</h2>
    <p class="co">${escapeHtml(job.company)} · ${escapeHtml(loc(job))} · ${escapeHtml(arrange(job.workArrangement))}</p>
    <p class="score" style="text-align:left">${job.matchScore}% match</p>
    <div class="chips">${visaChip(job.visaStatus)} ${job.experience ? `<span class="chip">${escapeHtml(job.experience)}</span>` : ""} ${job.salary && job.salary !== "Not specified" ? `<span class="chip">${escapeHtml(job.salary)}</span>` : ""}</div>
    <p class="meta">Posted ${escapeHtml(postedAgo(job.postedAt))} · Last verified ${escapeHtml(postedAgo(job.lastVerified))} · Source ${escapeHtml(job.source)}</p>
    <h3>Why it matches</h3>
    <div class="reasons">${(job.matchReasons||[]).map((r)=>`<span>✓ ${escapeHtml(r)}</span>`).join("") || "—"}</div>
    ${(job.missingRequirements||[]).length ? `<h3>Missing</h3><p class="missing">${escapeHtml(job.missingRequirements.join(", "))}</p>` : ""}
    ${(job.concerns||[]).length ? `<h3>Concerns</h3><p class="missing">${escapeHtml(job.concerns.join(", "))}</p>` : ""}
    <h3>Visa evidence</h3>
    ${(job.visaEvidence||[]).length ? job.visaEvidence.map((e)=>`<p class="evidence">“${escapeHtml(e)}”</p>`).join("") : `<p class="missing">No sponsorship language found. Status is unknown — verify on the employer site.</p>`}
    <h3>Description</h3>
    <div class="desc">${escapeHtml(job.description || "No description provided.")}</div>
    <h3>Application tracking</h3>
    <div class="form-grid two">
      <label>Status<select id="m-status">${STATUSES.map(([v,l]) => `<option value="${v}" ${rec.status===v?"selected":""}>${l}</option>`).join("")}</select></label>
      <label>Application date<input id="m-applied" type="date" value="${escapeHtml(rec.appliedAt||"")}" /></label>
      <label>Recruiter<input id="m-rec" value="${escapeHtml(rec.recruiter||"")}" /></label>
      <label>Recruiter email<input id="m-email" type="email" value="${escapeHtml(rec.recruiterEmail||"")}" /></label>
      <label>Follow-up<input id="m-follow" type="date" value="${escapeHtml(rec.followUpAt||"")}" /></label>
      <label>Interview<input id="m-int" type="date" value="${escapeHtml(rec.interviewAt||"")}" /></label>
      <label>Resume version<input id="m-resume" value="${escapeHtml(rec.resumeVersion||"")}" /></label>
    </div>
    <label>Notes<textarea id="m-notes" rows="3">${escapeHtml(rec.notes||"")}</textarea></label>
    <label>Cover letter<textarea id="m-cover" rows="3">${escapeHtml(rec.coverLetter||"")}</textarea></label>
    <div class="actions">
      <a class="btn btn-primary" href="${escapeHtml(job.applyUrl)}" target="_blank" rel="noopener">Apply</a>
      <button class="btn btn-secondary" id="m-save">${state.saved.includes(job.id)?"Unsave":"Save"}</button>
      <button class="btn btn-ghost" id="m-applied-btn">Mark applied</button>
      <button class="btn btn-ghost" id="m-skip">Skip</button>
    </div>
  </div>`;
  modal.querySelector(".close").onclick = closeModal;
  modal.onclick = (e) => { if (e.target === modal) closeModal(); };
  const persist = () => {
    state.applications[job.id] = {
      jobId: job.id,
      status: document.getElementById("m-status").value,
      notes: document.getElementById("m-notes").value,
      appliedAt: document.getElementById("m-applied").value,
      recruiter: document.getElementById("m-rec").value,
      recruiterEmail: document.getElementById("m-email").value,
      followUpAt: document.getElementById("m-follow").value,
      interviewAt: document.getElementById("m-int").value,
      resumeVersion: document.getElementById("m-resume").value,
      coverLetter: document.getElementById("m-cover").value,
    };
    saveStore();
  };
  ["m-status","m-applied","m-rec","m-email","m-follow","m-int","m-resume","m-notes","m-cover"].forEach((id) => {
    const n = document.getElementById(id);
    if (n) n.onchange = n.oninput = persist;
  });
  document.getElementById("m-save").onclick = () => { toggleSave(job.id); openModal(job); };
  document.getElementById("m-applied-btn").onclick = () => {
    document.getElementById("m-status").value = "applied";
    if (!document.getElementById("m-applied").value) document.getElementById("m-applied").value = new Date().toISOString().slice(0, 10);
    persist();
    openModal(job);
  };
  document.getElementById("m-skip").onclick = () => {
    if (!state.skipped.includes(job.id)) state.skipped.push(job.id);
    saveStore();
    closeModal();
    render();
  };
}
function closeModal() {
  document.getElementById("modal").classList.add("hidden");
  state.selected = null;
}
function toggleSave(id) {
  const i = state.saved.indexOf(id);
  if (i >= 0) state.saved.splice(i, 1);
  else state.saved.push(id);
  saveStore();
  render();
}

function bindCards(root) {
  root.querySelectorAll(".open").forEach((b) => b.onclick = () => {
    const job = scoredJobs().find((j) => j.id === b.dataset.id);
    if (job) openModal(job);
  });
  root.querySelectorAll(".save").forEach((b) => b.onclick = () => toggleSave(b.dataset.id));
}

function render() {
  const path = route();
  document.querySelectorAll(".nav a").forEach((a) => a.classList.toggle("active", a.getAttribute("data-route") === path));
  const jobs = scoredJobs();
  const main = document.getElementById("main");
  const pages = {
    "/": () => dashboard(jobs),
    "/jobs": () => listPage("Recommended", "All open roles, ranked by how they fit your profile.", "/jobs", jobs),
    "/visa": () => listPage("Visa sponsorship", "Only roles where the posting mentions sponsorship or strong relocation support.", "/visa", jobs),
    "/remote": () => listPage("Remote roles", "Remote and distributed postings. Use region filters for USA, Europe, UK, Canada, APAC, India, or anywhere.", "/remote", jobs),
    "/matches": () => listPage("High match", "Roles scoring 70% or higher against your profile.", "/matches", jobs),
    "/saved": () => listPage("Saved jobs", "Bookmarks stay in this browser.", "/saved", jobs),
    "/applications": () => applicationsPage(jobs),
    "/profile": () => profilePage(),
  };
  main.innerHTML = (pages[path] || pages["/"])();
  bindFilters();
  bindCards(main);
  const form = document.getElementById("profile-form");
  if (form) {
    form.onsubmit = (e) => {
      e.preventDefault();
      const fd = new FormData(form);
      const csv = (k) => String(fd.get(k) || "").split(",").map((s) => s.trim()).filter(Boolean);
      state.profile = {
        ...state.profile,
        name: fd.get("name"),
        headline: fd.get("headline"),
        yearsExperience: Number(fd.get("yearsExperience")) || 0,
        location: fd.get("location"),
        skills: csv("skills"),
        preferredTitles: csv("preferredTitles"),
        preferredTechnologies: csv("preferredTechnologies"),
        preferredIndustries: csv("preferredIndustries"),
        preferredCountries: csv("preferredCountries"),
        remotePreference: fd.get("remotePreference"),
        visaPreference: fd.get("visaPreference"),
        relocation: form.querySelector('[name="relocation"]').checked,
      };
      saveStore();
      location.hash = "#/jobs";
    };
    document.getElementById("reset-profile").onclick = () => { state.profile = { ...DEFAULT_PROFILE }; saveStore(); render(); };
  }
}

async function boot() {
  loadStore();
  const menu = document.getElementById("menu-btn");
  const sidebar = document.getElementById("sidebar");
  const back = document.getElementById("drawer-backdrop");
  menu.onclick = () => { sidebar.classList.add("open"); back.classList.remove("hidden"); };
  back.onclick = () => { sidebar.classList.remove("open"); back.classList.add("hidden"); };
  document.querySelectorAll(".nav a").forEach((a) => a.addEventListener("click", () => { sidebar.classList.remove("open"); back.classList.add("hidden"); }));
  window.addEventListener("hashchange", render);
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeModal(); });
  try {
    const res = await fetch("jobs.json", { cache: "no-store" });
    if (!res.ok) throw new Error("Could not load jobs");
    const data = await res.json();
    state.jobs = data.jobs || [];
    state.updatedAt = data.updated_at;
  } catch (err) {
    document.getElementById("main").innerHTML = `<div class="empty"><h2>Could not load jobs</h2><p>${escapeHtml(err.message)}</p></div>`;
    return;
  }
  render();
}
boot();
