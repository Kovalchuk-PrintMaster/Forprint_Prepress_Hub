# ОБОВ’ЯЗКОВИЙ СТАРТ ДЛЯ НОВОЇ AI-ПОМІЧНИЦІ

**Не виконуй patch/Make/CLI до завершення цієї процедури.**

## A. Read → Inspect → Reconcile
1. Прочитай `00_START_HERE.md`, Goal Contract, Decisions, Skeleton, Roadmap, Acceptance і `technical_unknowns.md`.
2. Відкрий реальний репозиторій/модуль, `make help`, поточний `git status`, тести, canonical contract refs, completion/attempt evidence. Визнач HEAD і staged/unstaged/untracked зміни.
3. **Не вважай цей ZIP canonical truth про поточний код:** описує стан станом на повідомлення 16–18.10.2026; приватні робочі GC16–GC17.2 файли можуть відрізнятися від remote Git.
4. Зістав Goal і фактичну реалізацію. Класифікуй `VERIFIED / PARTIAL / UNVERIFIED / BLOCKED / CANDIDATE` по кожному функціоналу.

## B. Improve → Proposal
5. Знайди дублювання, великі ad-hoc patch cycles, технічний борг, недобудовані ланцюжки та зайві ручні переходи; пропонуй проєктні Make/CLI функції замість повторних чат-скриптів.
6. За потреби перевір сучасні технології/API через актуальні авторитетні джерела; оцінюй реальну користь, сумісність, безпеку, вартість і rollback. Не мігруй лише через «новіше».
7. Сформуй короткий `Reassessment Proposal`: знайдене, докази, ризики, вплив на повний roadmap, що потребує санкції, а що можна безпечно продовжити.

## C. Execute only authorized bounded step
8. Перевір `Step Acceptance Contract` (input/output/tests/negative/evidence/review).
9. Не змінюй погоджену мету, не переписуй робочі схеми без окремого дозволу, не інтегруй автоматично у Git чи Prepress Hub, не вмикай production, customer messaging, DUAL sender.
10. Після кроку: зафіксуй фактичні докази, статус, невизначеність, наступний крок і онови дорожню карту кандидатним review.

## СТРОГО РОЗРІЗНЯЙ
- Machine technical pass vs real native Illustrator proof.
- Operator review vs client approval vs production release.
- Committed Git vs uncommitted server worktree.
- Current CLI implementation vs synthetic future proposal.
- Private client data vs public repository docs.

## Контракт спілкування
Українською; не проси повторно вже погоджене. Якщо з'явився справжній blocking gray zone, постав максимум 1–3 конкретні питання з доказом впливу, а не розпочинай нове загальне опитування.
