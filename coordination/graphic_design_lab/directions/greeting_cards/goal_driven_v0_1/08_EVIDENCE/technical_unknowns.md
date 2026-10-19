# Технічні сірі зони для доказового закриття

Це **не новий раунд загальних питань до керівника**; це перелік перевірок коду, джерел і runtime, які можна виконувати під час R0–R3.

| ID | Статус | Питання | Як закрити |
|---|---|---|---|
| U01 | UNVERIFIED | Чи s01 досі на HEAD 75b19ef і які GC16–GC17.2 зміни не відкомічені? | read-only git status/diff + tests |
| U02 | PARTIAL | Як фактично виражені обидва варіанти P01, точні розміри й логотипні source keys? | Builder/fixtures + PDF screenshot audit |
| U03 | PARTIAL | Назви/походження 2 типів рамок та 3 профілів підпису, стан DUAL | resource registry + release gates |
| U04 | PARTIAL | Чи page4 GC16 150×180/opacity .25 однаково працює у PDF і Native AI? | artifact geometry + visual parity |
| U05 | UNVERIFIED | Чи під час shrink-to-fit є надійний detector нечитабельності / exact text fidelity? | hostile long text tests |
| U06 | UNVERIFIED | Як Intake складає машинні Creator prompts і закриває rework? | real prompt packages and executed traces |
| U07 | UNVERIFIED | Які source/target hashes і операторські права покриває Handoff ZIP? | Handoff CLI + negative tests |
| U08 | UNVERIFIED | Як Windows Worker поведе себе під час RDP disconnect/reboot і error87? | isolated experiments on 192.168.50.69 |
| U09 | UNVERIFIED | Чи PDF фінально відповідає конкретним print-spec листівки? | operator print profile confirmation |
| U10 | UNVERIFIED | Які в GDL серверні canonical assets і механізм selective restore? | owner registry + scratch restore |
| U11 | NOT_IMPLEMENTED | Conditional PNG+TXT diagnostic contract | profile ID crosswalk + implementation tests |
| U12 | NOT_IMPLEMENTED | Одна спільна LayoutSpec схема PDF/AI | compare current schemas + rollout plan |
| U13 | NOT_TESTED | 3 різні end-to-end замовлення і операторські приймання | scenario gate R4 |
| U14 | FUTURE | Візуально-семантичний реєстр орглоготипів і конструктор GUI | v2 spec, no v1 blocker |
| U15 | FUTURE | failover Windows worker та cloud Illustrator API | separate architecture path, no v1 blocker |
| U16 | VERIFIED_IN_CURRENT_WORKTREE | Тематичний Assistant Context Pack включає 19/19 документів Goal-Driven; це ще не підтвердження їхньої канонічної Git-інтеграції | `make assistant-context-pack SCOPE=bootstrap TOPICS=graphic_design_lab`: handoff PASS, topics `graphic_design_lab`, 210 файлів, 19/19 Goal-Driven; повторити перевірку після Git commit |

Всі числові координати зі старих вимірів — `HISTORICAL_REFERENCE`, доки не звірені з актуальним runtime. Якщо зміна може впливати на погоджену мету, потрібен операторський review, а не припущення.
