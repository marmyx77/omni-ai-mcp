# Diagnosi: gemini-3.8-flash in omni-ai-mcp

Origine: sessione Claude "isms-bc" (cartella ISMS), 2026-09-19, su richiesta di Marco.
Fatti verificati con chiamate reali e lettura del codice. Nessuna modifica applicata da quella sessione.
File di lavoro, non da committare: cancellarlo quando letto.

## 1. Il modello esiste ed è raggiungibile

- `ask_model(model="gemini-3.8-flash", provider="gemini")` risponde.
- `ask_model(model="google/gemini-3.8-flash", provider="openrouter")` risponde.
- Controllo negativo: `gemini-99.9-flash` dà 404 NOT_FOUND su Gemini, `google/gemini-99.9-flash` dà HTTP 400 su OpenRouter. Le risposte sopra non sono un fallback silenzioso.

## 2. Quale codice gira davvero nelle sessioni aperte

- Sei processi `python3.14 -m app.server` vivi. Con `-m` il cwd va in testa a `sys.path`, quindi:
  - il processo avviato con cwd su questo repo (PID 21251) usa il working tree;
  - gli altri (es. PID 16224, cwd `~/Contents/ISMS`) usano `/opt/homebrew/lib/python3.14/site-packages/app`, cioè omni_ai_mcp **4.0.0**.
- L'installazione non è editabile (nessun `direct_url.json`). Le modifiche qui arrivano alle altre sessioni solo dopo reinstallazione e riavvio. Il registro ha una cache con TTL di 3600 s.
- Divergono 11 file tra installato e working tree (config.py, server.py, model_registry.py, openrouter.py, ask_gemini.py, ask_model.py, challenge.py, deep_research.py, analyze_image.py, generate_image.py, `__init__.py`).

## 3. Le env arrivano, ma nella 4.0.0 le usa solo metà del codice

- `~/.claude.json` → `mcpServers.omni-ai-mcp.env`: `GEMINI_MODEL_PRO=gemini-3.8-flash` e `GEMINI_MODEL_FLASH=gemini-3.8-flash`. Verificato con `ps eww` che entrambe sono nell'ambiente dei processi vivi; `config.model_pro` e `config.model_flash` valgono entrambi `gemini-3.8-flash`.
- Percorso che rispetta le env: il dict `MODELS` in `app/services/gemini.py`. Lo usano ask_gemini, analyze_codebase, generate_code, analyze_image, file_search, web_search. Con questa env l'alias `pro` di ask_gemini usa 3.8 Flash, non 3.1 Pro.
- Percorso che le ignora (4.0.0): `model_registry.resolve()` percorre prima `CATEGORY_PRIORITIES` cablata (3.1-pro-preview, 3.1-flash, 2.5-flash...) e usa il valore da env solo se nessun candidato è disponibile. Da lì passano `_resolve_gemini_model` in ask_model (alias pro/flash/fast/flash-lite) e il report di `gemini_list_models`. Risultato: ask_model con alias `flash` usa 2.5 Flash e il report stampa "Text Pro: gemini-3.1-pro-preview, Text Flash: gemini-2.5-flash" mentre ask_gemini sta usando 3.8. Report fuorviante.
- La riscrittura v4.6.0 nel working tree risolve questo punto: env vince (`app/services/model_registry.py:262-265`), 3.8 nei fallback (`:69`), report con provenienza. Bene.

## 4. Punti che la riscrittura non copre ancora (verificati nel working tree)

1. **L'override env vince senza validazione e spegne l'auto-detect.** Con `GEMINI_MODEL_PRO=gemini-3.8-flash` in `~/.claude.json`, `text_pro` non farà mai auto-detect e `pro` resterà 3.8 Flash. Da decidere con Marco: togliere le due env da `~/.claude.json` per lasciar lavorare l'auto-detect, oppure tenerle se è voluto. Inoltre `Resolution(override, "env", ...)` restituisce il valore così com'è anche se non compare nella discovery: un refuso nella env fallirebbe solo alla prima chiamata. Valutare un warning quando l'override non è tra i modelli scoperti.
2. **Descrizioni stantie** in `app/tools/text/ask_gemini.py:30` e `:41` ("pro (Gemini 3 ...)", "flash (2.5 ...)", "For 2.5 models uses budget instead"). Con l'auto-detect non descrivono più la realtà.
3. **Il ramo thinking decide sull'alias, non sul modello** (`app/tools/text/ask_gemini.py:183-190`): `model == "pro"` → `thinking_level`, altrimenti `thinking_budget`. Ora che `flash`/`fast` risolvono a un modello 3.x (3.8 Flash), la richiesta parte con `thinking_budget`, parametro pensato per i 2.5. Da verificare se l'API 3.x lo accetta o pretende `thinking_level`. Suggerimento: decidere sul `model_id` risolto (major ≥ 3 → `thinking_level`).
4. `check_deprecated` nella 4.0.0 segnala `model_image_pro=gemini-3.1-pro-image-preview` come assente dalla discovery.

## 5. Dopo la modifica

Reinstallare il pacchetto (o avviare il server con cwd sul repo) e riavviare le sessioni: quelle aperte tengono in memoria la 4.0.0 e la cache del registro.
