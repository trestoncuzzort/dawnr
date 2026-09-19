# Skills and agents pulled from the lab workstation

The full text of everything indexed here lives in `/home/t/lab-pull/claude`: 145 skills under
`/home/t/lab-pull/claude/skills/<name>/SKILL.md`, each with its bundled references and scripts beside it, and 33
agent definitions at `/home/t/lab-pull/claude/agents/<name>.md`. That is 1,172 files, about 18 MB.

They were pulled from the lab workstation on 2026-09-19. They are third-party material. Each carries its own licence
and its own author: 63 of the 145 skills declare a licence in their frontmatter (MIT, Apache-2.0, BSD-3-Clause,
CC BY-NC-SA 4.0, and four marked proprietary with a `LICENSE.txt` beside the skill) and the other 82 declare
none. So they are indexed here rather than copied into this repository. Read them where they sit. Nothing under
`/home/t/lab-pull/claude` is changed by this repository, and nothing from it is redistributed here.

To hand one to another agent, give it the path. A skill is its whole directory, and `SKILL.md` names the reference
files it expects to find alongside itself, so pass the directory or the `SKILL.md` path, not the description below.

Descriptions are taken from each file's own YAML frontmatter, cut to its opening sentence or two. They are the
author's words, not a summary written here: they say what the author intended, not what has been tried on this
project's work. Every skill declares both a name and a description, so nothing below is missing one.

## What is here

| Group | Skills |
|---|---|
| GSD — the project and phase loop | 17 |
| GSD — review, audit and debugging | 14 |
| GSD — milestones, shipping and project state | 10 |
| GSD — context, ideation and handoff | 16 |
| GSD — configuration and workspaces | 10 |
| Literature search, citation and reference management | 10 |
| Scientific writing, peer review and grants | 6 |
| Documents and office formats | 6 |
| Figures, diagrams, posters and slides | 10 |
| Method: hypotheses, experimental design and critique | 6 |
| Statistics | 4 |
| Data handling at scale | 5 |
| Machine learning and deep learning | 11 |
| Modelling, optimization and numerical computing | 6 |
| Compute, GPUs and shared-machine manners | 3 |
| Running and repairing background work | 5 |
| Building skills | 3 |
| Writing and code style | 3 |
| **Total** | **145** |

Plus 33 agent definitions, listed after the skills.

## Skills (145)

### GSD — the project and phase loop (17)

GSD is one installed toolkit, not many: 67 of the 145 skills and all 33 agents belong to it. The five GSD groups below split it by what each skill does. These are the main loop, from a new project through to an executed phase.

- **gsd-new-project** — Initialize a new project with deep context gathering and PROJECT.md
- **gsd-new-milestone** — Start a new milestone cycle — update PROJECT.md and route to requirements
- **gsd-phase** — CRUD for phases in ROADMAP.md — add, insert, remove, or edit phases
- **gsd-spec-phase** — Clarify WHAT a phase delivers with ambiguity scoring; produces a SPEC.md before discuss-phase.
- **gsd-discuss-phase** — Gather phase context through adaptive questioning before planning.
- **gsd-plan-phase** — Create detailed phase plan (PLAN.md) with verification loop
- **gsd-execute-phase** — Execute all plans in a phase with wave-based parallelization
- **gsd-verify-work** — Validate built features through conversational UAT
- **gsd-progress** — Check progress, advance workflow, or dispatch freeform intent — the unified GSD situational command
- **gsd-autonomous** — Run all remaining phases autonomously — discuss→plan→execute per phase
- **gsd-quick** — Execute a quick task with GSD guarantees (atomic commits, state tracking) but skip optional agents
- **gsd-fast** — Execute a trivial task inline — no subagents, no planning overhead
- **gsd-mvp-phase** — Plan a phase as a vertical MVP slice — user story, SPIDR splitting, then plan-phase
- **gsd-ai-integration-phase** — Generate an AI-SPEC.md design contract for phases that involve building AI systems.
- **gsd-ui-phase** — Generate UI design contract (UI-SPEC.md) for frontend phases
- **gsd-add-tests** — Generate tests for a completed phase based on UAT criteria and implementation
- **gsd-ns-workflow** — workflow | discuss plan execute verify phase progress

### GSD — review, audit and debugging (14)

- **gsd-code-review** — Review source files changed during a phase for bugs, security issues, and code quality problems
- **gsd-review** — Request cross-AI peer review of phase plans from external AI CLIs
- **gsd-plan-review-convergence** — Cross-AI plan convergence loop — replan with review feedback until no HIGH concerns remain.
- **gsd-audit-fix** — Autonomous audit-to-fix pipeline — find issues, classify, fix, test, commit
- **gsd-audit-milestone** — Audit milestone completion against original intent before archiving
- **gsd-audit-uat** — Cross-phase audit of all outstanding UAT and verification items
- **gsd-secure-phase** — Retroactively verify threat mitigations for a completed phase
- **gsd-validate-phase** — Retroactively audit and fill Nyquist validation gaps for a completed phase
- **gsd-eval-review** — Audit an executed AI phase's evaluation coverage and produce an EVAL-REVIEW.md remediation plan.
- **gsd-ui-review** — Retroactive 6-pillar visual audit of implemented frontend code
- **gsd-debug** — Systematic debugging with persistent state across context resets
- **gsd-forensics** — Post-mortem investigation for failed GSD workflows — diagnoses what went wrong.
- **gsd-undo** — Safe git revert. Roll back phase or plan commits using the phase manifest with dependency checks.
- **gsd-ns-review** — quality gates | code review debug audit security eval ui

### GSD — milestones, shipping and project state (10)

- **gsd-complete-milestone** — Archive completed milestone and prepare for next version
- **gsd-milestone-summary** — Generate a comprehensive project summary from milestone artifacts for team onboarding and review
- **gsd-review-backlog** — Review and promote backlog items to active milestone
- **gsd-ship** — Create PR, run review, and prepare for merge after verification passes
- **gsd-pr-branch** — Create a clean PR branch by filtering out .planning/ commits — ready for code review
- **gsd-inbox** — Triage and review open GitHub issues and PRs against project templates and contribution guidelines.
- **gsd-stats** — Display project statistics — phases, plans, requirements, git metrics, and timeline
- **gsd-cleanup** — Archive accumulated phase directories from completed milestones
- **gsd-health** — Diagnose planning directory health and optionally repair issues
- **gsd-ns-project** — project lifecycle | milestones audits summary

### GSD — context, ideation and handoff (16)

- **gsd-capture** — Capture ideas, tasks, notes, and seeds to their destination
- **gsd-explore** — Socratic ideation and idea routing — think through ideas before committing to plans
- **gsd-sketch** — Sketch UI/design ideas with throwaway HTML mockups, or propose what to sketch next (frontier mode)
- **gsd-spike** — Spike an idea through experiential exploration, or propose what to spike next (frontier mode)
- **gsd-graphify** — Build, query, and inspect the project knowledge graph in .planning/graphs/
- **gsd-map-codebase** — Analyze codebase with parallel mapper agents to produce .planning/codebase/ documents
- **gsd-docs-update** — Generate or update project documentation verified against the codebase
- **gsd-ingest-docs** — Bootstrap or merge a .planning/ setup from existing ADRs, PRDs, SPECs, and docs in a repo.
- **gsd-import** — Ingest external plans with conflict detection against project decisions before writing anything.
- **gsd-extract-learnings** — Extract decisions, lessons, patterns, and surprises from completed phase artifacts
- **gsd-pause-work** — Create context handoff when pausing work mid-phase
- **gsd-resume-work** — Resume work from previous session with full context restoration
- **gsd-thread** — Manage persistent context threads for cross-session work
- **gsd-profile-user** — Generate developer behavioral profile and create Claude-discoverable artifacts
- **gsd-ns-context** — codebase intelligence | map graphify docs learnings
- **gsd-ns-ideate** — exploration capture | explore sketch spike spec capture

### GSD — configuration and workspaces (10)

- **gsd-config** — Configure GSD settings — workflow toggles, advanced knobs, integrations, and model profile
- **gsd-settings** — Configure GSD workflow toggles and model profile
- **gsd-surface** — Toggle which skills are surfaced — apply a profile, list, or disable a cluster without reinstall
- **gsd-update** — Update GSD to latest version with changelog display
- **gsd-help** — Show available GSD commands and usage guide
- **gsd-manager** — Interactive command center for managing multiple phases from one terminal
- **gsd-workspace** — Manage GSD workspaces — create, list, or remove isolated workspace environments
- **gsd-workstreams** — Manage parallel workstreams — list, create, switch, status, progress, complete, and resume
- **gsd-ultraplan-phase** — [BETA] Offload plan phase to Claude Code's ultraplan cloud; review in browser and import back.
- **gsd-ns-manage** — config workspace | workstreams thread update ship inbox

### Literature search, citation and reference management (10)

- **citation-management** — Comprehensive citation management for academic research. Search OpenAlex, PubMed, and Google Scholar for papers, extract accurate metadata, validate citations, and generate properly formatted BibTeX entries.
- **literature-review** — Conduct comprehensive, systematic literature reviews using multiple academic databases (PubMed, arXiv, bioRxiv, Semantic Scholar, etc.).
- **paper-lookup** — Search 11 academic literature APIs for papers, preprints, citations, and open-access full text, and return results with reproducible provenance.
- **paperclip** — Search and read full-text biomedical papers, FDA/PMDA/EMA regulatory documents, clinical trial registries, and UniProt/PDB/ChEMBL entries with the Paperclip CLI from GXL.
- **paperzilla** — Chat with your agent about projects, recommendations, and canonical papers in Paperzilla.
- **pyzotero** — Interact with Zotero reference management libraries using the pyzotero Python client.
- **research-lookup** — Compile current scholarly evidence for a scientific manuscript or research brief.
- **database-lookup** — Query documented public database APIs with explicit endpoints, filters, pagination, and provenance.
- **exa-search** — Web toolkit powered by Exa, tuned for scientific and technical content.
- **parallel-web** — Use Parallel CLI for web search, URL extraction, deep research, structured data enrichment, entity discovery, and recurring web monitoring.

### Scientific writing, peer review and grants (6)

- **scientific-writing** — Draft, revise, and audit scientific manuscripts or reports with explicit evidence provenance, reporting-guideline coverage, authorship accountability, confidentiality controls, and local consistency checks.
- **peer-review** — Prepare evidence-bounded, constructive peer-review drafts and structured manuscript assessments.
- **scholar-evaluation** — Provide qualitative-first, evidence-traceable developmental review of scholarly works and audit low-stakes research-assessment rubrics with optional local quality controls.
- **research-grants** — Write competitive research proposals for NSF, NIH, DOE, DARPA, and Taiwan NSTC.
- **venue-templates** — Prepare journal manuscripts, conference papers, research posters, and grant documents using venue-specific formatting guidance and bundled LaTeX scaffolds.
- **markdown-mermaid-writing** — Comprehensive markdown and Mermaid diagram writing skill. Use when creating any scientific document, report, analysis, or visualization.

### Documents and office formats (6)

- **sci-docx** — Use this skill whenever the user wants to create, read, edit, or manipulate Word documents (.docx files) or Word templates (.dotx files).
- **sci-pdf** — Use this skill whenever the user wants to do anything with PDF files. This includes reading or extracting text/tables from PDFs, combining or merging multiple PDFs into one, splitting PDFs apart, rotating pages, adding watermarks, creating …
- **sci-pptx** — Use this skill any time a .pptx or .potx file is involved in any way — as input, output, or both.
- **sci-xlsx** — Create, edit, analyze, or convert Excel spreadsheets (.xlsx, .xlsm, .xltx) where the workbook file is the primary deliverable.
- **liteparse** — Local document and PDF parsing that returns spatial text with bounding boxes.
- **markitdown** — Convert heterogeneous documents and selected URIs to Markdown with Microsoft MarkItDown for text analysis, search, and LLM/RAG ingestion.

### Figures, diagrams, posters and slides (10)

- **scientific-visualization** — Create and audit truthful, accessible, publication-ready scientific figures with Matplotlib, Seaborn, or Plotly.
- **matplotlib** — Low-level plotting library for full customization. Use when you need fine-grained control over every plot element, creating novel plot types, or integrating with specific scientific workflows.
- **seaborn** — Statistical visualization with pandas integration. Use for quick exploration of distributions, relationships, and categorical comparisons with attractive defaults.
- **d3-viz** — Creating interactive data visualisations using d3.js. This skill should be used when creating custom charts, graphs, network diagrams, geographic visualisations, or any complex SVG-based data visualisation that requires fine-grained …
- **scientific-schematics** — Create publication-quality scientific diagrams using Nano Banana 2 AI with smart iterative refinement.
- **infographics** — Create professional infographics using Nano Banana Pro AI with smart iterative refinement.
- **generate-image** — Generate or edit images with AI models through the OpenRouter Image API (Gemini, Seedream, Recraft, GPT-Image, Riverflow).
- **latex-posters** — Create professional research posters in LaTeX using beamerposter, tikzposter, or baposter.
- **pptx-posters** — Create and audit editable scientific posters in macro-free PowerPoint (.pptx) from author-approved local content and assets.
- **scientific-slides** — Build slide decks and presentations for research talks. Use this for making PowerPoint slides, conference presentations, seminar talks, research presentations, thesis defense slides, or any scientific talk.

### Method: hypotheses, experimental design and critique (6)

- **hypothesis-generation** — Formulate evidence-bounded scientific questions, candidate hypotheses, rival explanations, causal or associational claims, discriminating predictions, measurements, and preregistration-ready analysis plans.
- **hypogenic** — Plans and audits use of ChicagoHAI HypoGeniC/HypoRefine for LLM-assisted hypothesis generation from labeled text datasets.
- **scientific-brainstorming** — Facilitates evidence-aware scientific ideation with independent generation, structured discussion, explicit assumptions, transparent evaluation, adversarial review, and decision logs.
- **scientific-critical-thinking** — Evaluate scientific claims and evidence quality. Use for assessing experimental design validity, identifying biases and confounders, applying evidence grading frameworks (GRADE, Cochrane Risk of Bias), or teaching critical analysis.
- **experimental-design** — Design experiments and studies BEFORE data is collected — choosing a design, randomizing, blocking, and laying out treatment combinations so results are interpretable.
- **what-if-oracle** — Run structured What-If scenario analysis with 4–6 branch possibility exploration (best, likely, worst, wild card, contrarian, second-order).

### Statistics (4)

- **statistical-analysis** — Guided statistical analysis for research data - test selection, assumption checking, effect sizes, power analysis, Bayesian alternatives, and APA-formatted reporting.
- **statistical-power** — Sample-size and statistical power calculations for planning studies. Use whenever someone asks "how many subjects/samples/replicates do I need", wants an a priori power analysis, a minimum detectable effect (MDE), a power curve, or needs …
- **statsmodels** — Statistical models library for Python. Use when you need specific model classes (OLS, GLM, mixed models, ARIMA) with detailed diagnostics, residuals, and inference.
- **pymc** — Bayesian modeling with PyMC. Build hierarchical models, MCMC (NUTS), variational inference, LOO/WAIC comparison, posterior checks, for probabilistic programming and inference.

### Data handling at scale (5)

- **exploratory-data-analysis** — Perform bounded, local exploratory analysis of explicitly supported scientific files.
- **polars** — High-performance DataFrame library for Python ETL, analytics, and pandas migration.
- **dask** — Distributed computing for larger-than-RAM pandas/NumPy workflows. Use when you need to scale existing pandas/NumPy code beyond memory or across clusters.
- **vaex** — Use this skill for processing and analyzing large tabular datasets (billions of rows) that exceed available RAM.
- **zarr-python** — Chunked N-D arrays for cloud storage (Zarr-Python 3). Compressed arrays, parallel I/O, S3/GCS via fsspec, NumPy/Dask/Xarray compatible, for large-scale scientific computing pipelines.

### Machine learning and deep learning (11)

- **scikit-learn** — Machine learning in Python with scikit-learn. Use when working with supervised learning (classification, regression), unsupervised learning (clustering, dimensionality reduction), model evaluation, hyperparameter tuning, preprocessing, or …
- **transformers** — Hugging Face Transformers for loading Hub models, running pipeline inference, text generation, and Trainer fine-tuning on NLP, vision, audio, and multimodal tasks.
- **pytorch-lightning** — Deep learning framework (PyTorch Lightning / lightning package). Organize PyTorch code into LightningModules, configure Trainers for multi-GPU/TPU, implement data pipelines, callbacks, logging (W&B, TensorBoard, MLflow), distributed …
- **torch-geometric** — PyTorch Geometric (PyG) for graph neural networks — node/link/graph classification, message passing (GCN, GAT, GraphSAGE, GIN), heterogeneous graphs, neighbor sampling, and custom datasets.
- **aeon** — This skill should be used for time series machine learning tasks including classification, regression, clustering, forecasting, anomaly detection, segmentation, and similarity search.
- **timesfm-forecasting** — Zero-shot time series forecasting with Google's TimesFM foundation model.
- **umap-learn** — Use UMAP-learn for nonlinear dimensionality reduction, 2D/3D embeddings, clustering preprocessing, supervised or semi-supervised UMAP, DensMAP, AlignedUMAP, and Parametric UMAP workflows.
- **shap** — Explain and audit machine-learning predictions with SHAP. Use for selecting SHAP explainers and maskers, computing and validating feature attributions, handling multi-output explanations, and producing local or global SHAP visualizations.
- **stable-baselines3** — Production-ready reinforcement learning algorithms (PPO, SAC, DQN, TD3, DDPG, A2C) with scikit-learn-like API.
- **pufferlib** — Version-aware guidance for PufferLib reinforcement-learning environments, vectorization, policies, PuffeRL training, evaluation, and safe checkpoint review.
- **hugging-science** — Use when the user is doing AI/ML work in a scientific domain such as biology, chemistry, physics, astronomy, climate, genomics, materials, medicine, ecology, energy, engineering, math, drug discovery, protein …

### Modelling, optimization and numerical computing (6)

- **simpy** — Build, inspect, test, and analyze bounded process-based discrete-event simulations with SimPy, including events, resources, interrupts, monitoring, replications, warm-up, and reproducible output analysis.
- **pymoo** — Multi-objective optimization framework. NSGA-II, NSGA-III, MOEA/D, Pareto fronts, constraint handling, benchmarks (ZDT, DTLZ), for engineering design and optimization problems.
- **networkx** — Create, analyze, and visualize complex networks and graphs in Python with NetworkX.
- **matlab** — Build, review, migrate, and safely plan MATLAB or GNU Octave numerical workflows, including arrays, tabular/time data, tests, projects, graphics, MAT files, and explicit Python interoperability.
- **sympy** — Use when you need exact symbolic math in Python — algebra, calculus, equation solving, symbolic linear algebra, or code generation via lambdify/LaTeX.
- **uncertainty-and-units** — Track physical units and propagate measurement uncertainty in scientific calculations using pint and uncertainties.

### Compute, GPUs and shared-machine manners (3)

- **optimize-for-gpu** — GPU-accelerates scientific Python on NVIDIA hardware and verifies that the result is correct and faster.
- **modal** — Modal is a serverless cloud platform for running Python on demand, including on-demand GPUs.
- **cpu-yield** — Yield CPU to other users of this shared box by SUSPENDING our compute instead of killing it, and log an apology each time.

### Running and repairing background work (5)

- **workflow-model-policy** — Model-selection policy for the Workflow tool and for spawned subagents.
- **workflow-nanny** — Watch a background Workflow from the first second and diagnose it the moment it goes quiet, instead of waiting out a long stall threshold.
- **workflow-watchdog** — Check on running Workflow agents and repair a run that has stalled, looped, or returned empty.
- **workflow-salvage** — Recover the work of a Workflow run that was killed, interrupted, or died before finishing - including agents that never completed and therefore left NOTHING in journal.jsonl.
- **idle-repair** — Decide whether background work has actually stalled, and repair it by resuming from cached results rather than restarting.

### Building skills (3)

- **autoskill** — Observe the user's screen via screenpipe, detect repeated research workflows, match them against existing scientific-agent-skills, and draft new skills (or composition recipes that chain existing ones) for the …
- **skill-builder** — Automatically detect source types and build AI skills using Skill Seekers.
- **skill-seekers** — Automatically detect source types and build AI skills using Skill Seekers.

### Writing and code style (3)

- **unslop-text** — Strips the cues that make prose read as AI-generated and forces a deliberate human voice instead of the model's default register.
- **unslop-code** — Strips the tells that make source code read as AI-generated and forces code that fits the project instead of the model's default average.
- **unslop-ui** — Strips the cues that make a website read as AI-generated and forces a deliberate, project-specific design choice instead of the model's default.

`skill-seekers` and `skill-builder` carry the same description word for word; they appear to be the same skill
installed under two names.

## Agents (33)

Every one of the 33 agent definitions belongs to the GSD system, and each says which GSD command spawns it. They are
subagent definitions, not skills: a GSD skill invokes them.

### Research and planning (12)

- **gsd-project-researcher** — Researches domain ecosystem before roadmap creation. Produces files in .planning/research/ consumed during roadmap creation.
- **gsd-domain-researcher** — Researches the business domain and real-world application context of the AI system being built.
- **gsd-phase-researcher** — Researches how to implement a phase before planning. Produces RESEARCH.md consumed by gsd-planner.
- **gsd-ai-researcher** — Researches a chosen AI framework's official docs to produce implementation-ready guidance — best practices, syntax, core patterns, and pitfalls distilled for the specific use case.
- **gsd-advisor-researcher** — Researches a single gray area decision and returns a structured comparison table with rationale.
- **gsd-research-synthesizer** — Synthesizes research outputs from parallel researcher agents into SUMMARY.md.
- **gsd-assumptions-analyzer** — Deeply analyzes codebase for a phase and returns structured assumptions with evidence.
- **gsd-framework-selector** — Presents an interactive decision matrix to surface the right AI/LLM framework for the user's specific use case.
- **gsd-roadmapper** — Creates project roadmaps with phase breakdown, requirement mapping, success criteria derivation, and coverage validation.
- **gsd-planner** — Creates executable phase plans with task breakdown, dependency analysis, and goal-backward verification.
- **gsd-plan-checker** — Verifies plans will achieve phase goal before execution. Goal-backward analysis of plan quality.
- **gsd-pattern-mapper** — Analyzes codebase for existing patterns and produces PATTERNS.md mapping new files to closest analogs.

### Execution, debugging and verification (7)

- **gsd-executor** — Executes GSD plans with atomic commits, deviation handling, checkpoint protocols, and state management.
- **gsd-debugger** — Investigates bugs using scientific method, manages debug sessions, handles checkpoints.
- **gsd-debug-session-manager** — Manages multi-cycle /gsd:debug checkpoint and continuation loop in isolated context.
- **gsd-code-fixer** — Applies fixes to code review findings from REVIEW.md. Reads source files, applies intelligent fixes, and commits each fix atomically.
- **gsd-verifier** — Verifies phase goal achievement through goal-backward analysis. Checks codebase delivers what phase promised, not just that tasks completed.
- **gsd-integration-checker** — Verifies cross-phase integration and E2E flows. Checks that phases connect properly and user workflows complete end-to-end.
- **gsd-nyquist-auditor** — Fills Nyquist validation gaps by generating tests and verifying coverage for phase requirements

### Review and audit (4)

- **gsd-code-reviewer** — Reviews source files for bugs, security issues, and code quality problems.
- **gsd-security-auditor** — Verifies threat mitigations from PLAN.md threat model exist in implemented code.
- **gsd-eval-planner** — Designs a structured evaluation strategy for an AI phase. Identifies critical failure modes, selects eval dimensions with rubrics, recommends tooling, and specifies the reference dataset.
- **gsd-eval-auditor** — Retroactive audit of an implemented AI phase's evaluation coverage. Checks implementation against the AI-SPEC.md evaluation plan.

### Codebase intelligence and documentation (6)

- **gsd-codebase-mapper** — Explores codebase and writes structured analysis documents. Spawned by map-codebase with a focus area (tech, arch, quality, concerns).
- **gsd-intel-updater** — Analyzes codebase and writes structured intel files to .planning/intel/.
- **gsd-doc-classifier** — Classifies a single planning document as ADR, PRD, SPEC, DOC, or UNKNOWN.
- **gsd-doc-synthesizer** — Synthesizes classified planning docs into a single consolidated context.
- **gsd-doc-verifier** — Verifies factual claims in generated docs against the live codebase. Returns structured JSON per doc.
- **gsd-doc-writer** — Writes and updates project documentation. Spawned with a doc_assignment block specifying doc type, mode (create/update/supplement), and project context.

### Frontend and UI (3)

- **gsd-ui-researcher** — Produces UI-SPEC.md design contract for frontend phases. Reads upstream artifacts, detects design system state, asks only unanswered questions.
- **gsd-ui-checker** — Validates UI-SPEC.md design contracts against 6 quality dimensions. Produces BLOCK/FLAG/PASS verdicts.
- **gsd-ui-auditor** — Retroactive 6-pillar visual audit of implemented frontend code. Produces scored UI-REVIEW.md.

### Developer profiling (1)

- **gsd-user-profiler** — Analyzes extracted session messages across 8 behavioral dimensions to produce a scored developer profile with confidence levels and evidence.
