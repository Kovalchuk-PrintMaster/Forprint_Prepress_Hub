# ForPrint Design Lab · Goal-Driven Development + Greeting Card Constructor
**Integration review packet v0.1 · 18.10.2026 · Ukrainian · READ-ONLY / NO AUTHORIZATION**

## Навіщо цей пакет
Перенести з діалогу до проєкту 30 блоків погоджених управлінських принципів, цільову модель листівки, початкову карту виконання, правила приймання, контекст для наступної AI-помічниці й фактичні посилання на існуючий код та експерименти. Призначення — **основа для review та подальшої контрольованої інтеграції**, а не команда автоматично змінювати репозиторій чи запускати виробництво.

## Головна послідовність
**Goal → Product Skeleton → Requirements → Roadmap → Step Acceptance → Implementation → Evidence → Operator Review → Improvement**.
ТЗ готове до роботи, коли відома мета та її приймання, немає критичних сірих зон, а наступний виконавець може розпочати перевірюваний крок. Ідеальної деталізації всього майбутнього не потрібно.

## Документи
- `01_GOVERNANCE/goal_contract.yaml` — стратегічна мета та межі.
- `01_GOVERNANCE/decisions_01_30.yaml` — 30 погоджених рішень, походження і статус інтеграції.
- `01_GOVERNANCE/requirements_system_v0_1.md` — життєвий цикл ТЗ, реєстр, версії, переоцінка.
- `02_PRODUCT/greeting_card_skeleton_v0_1.yaml` — структура сторінок, відома геометрія, межі доказовості.
- `02_PRODUCT/product_behavior_v0_1.md` — повна функціональна специфікація листівки.
- `03_WORKFLOW/end_to_end_contract_v0_1.yaml` — Intake → Creator → Handoff → Builder → PDF → Operator.
- `03_WORKFLOW/windows_worker_future_v0_1.md` — Illustrator Worker та відкладений Cloud API.
- `04_ACCEPTANCE/acceptance_policy_v0_1.yaml`, `diagnostics_contract_v0_1.yaml`, `three_order_gate_v0_1.yaml` — моделі перевірки.
- `05_ROADMAP/roadmap_v0_1.yaml`, `roadmap_review.md` — макроетапи та деталізовані мікрокроки.
- `06_REUSE/tool_registry_seed_v0_1.yaml` — початковий список інструментів-кандидатів, без неправдивого статусу reusable.
- `07_ASSISTANT/START_HERE_ASSISTANT.md`, `ASSISTANT_CONTEXT_INSERT.md` — обов'язкова процедура вступу до роботи та вставка в context pack.
- `08_EVIDENCE/source_inventory_v0_1.yaml`, `technical_unknowns.md` — що доведено, де перевіряти, що не перевірено.
**Архівні додатки початкового інтеграційного ZIP (не включені до цієї Git-теки):**
- `09_REVIEW/GC18_Goal_Driven_Architecture_Review_v0_1.pdf` — PDF-огляд початкового ZIP.
- `90_INTEGRATION/` — валідатор та інструкції початкового ZIP.
- `99_MANIFEST/files_sha256.json` — контроль цілісності початкового ZIP.
Ці шляхи належать вихідному пакету, а не поточному набору 19 Git-документів.

## Правила безпеки
1. **Жодних патчів, commit, push, зміни SMB, production write, автоматичного схвалення чи відправлення клієнту.**
2. Перш ніж переносити документи в репозиторій, звірити поточну гілку, незакомічену роботу GC16/GC17/GC18 та фактичні YAML/скрипти.
3. Не створювати паралельну «істину»: нові файли — candidate-документація, яку потрібно прив'язати до чинного каталогу та Assistant Context Pack.
4. Не відтворювати персональні листівки і не додавати приватні логотипи/підписи в Git. Пакет не містить клієнтських медіа.
5. Технічний PASS ≠ завершений етап ≠ операторське погодження ≠ публікація ≠ друкарський дозвіл.

## Стан джерел
Останній наданий лог `s01`: 652 passed, 1 тестове попередження; кандидат r006 з чотирма PDF / 16 PNG; незакомічені GC16–GC17.2 зміни. GC18-A2 має позитивне **візуальне** погодження нативного AreaText та вертикального центрування. Full Windows Worker, 3 end-to-end успіхи та єдиний LayoutSpec **ще не доведені**.
