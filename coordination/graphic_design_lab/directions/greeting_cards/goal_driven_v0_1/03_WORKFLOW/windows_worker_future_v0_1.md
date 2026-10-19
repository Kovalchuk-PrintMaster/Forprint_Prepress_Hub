# GC18 Native Illustrator Worker · scope & boundaries

## Поточний proof (16.10.2026)
Windows 10 19045 на `192.168.50.69`, обліковий запис `prepress\work`, активний RDP-сеанс на момент інвентаризації, Illustrator 2022/24/25/26. Python `WindowsApps/python.exe` не підтверджує встановлений інтерпретатор. GC18-A1: Illustrator 2026 створив нативний 1 AreaText 150×180 мм + чотири окремі sender lines. GC18-A2: користувач візуально погодив vertical center. Windows `LoadLibrary failed error 87` був у попередньому експерименті, причина невстановлена; тестувати RDP session lifecycle окремо.

## Мета A3 → Worker
Окремий Illustrator Worker працює у Windows interactive user session, але без щоденної участі дизайнера. `s01` — автор завдання, Worker — виконавець. Локальне staging, source hash, дозволені підписані/зафіксовані проєктні скрипти, один job at a time, таймаут/ACK, machine evidence. Завдання повертає AI+PDF/PNG; клієнтська SMB тека — лише робочий інтерфейс. Жоден крок не повинен залежати від випадково відкритого документа Illustrator.

## Наступний виділений комп'ютер
Worker registry + capability matching (Illustrator version, fonts, RAM/OS, assets); не хардкодити IP. Пізніша можливість кількох машин і failover вимагає leases, fencing/stale owner proof та ідемпотентності. Не припускати, що штатний Illustrator коректно працює в Windows Service/session 0 або після Sign out; підтверджувати RDP disconnect/lock/reboot спеціальними тестами.

## Adobe API
Другий backend лише FUTURE_EXPLORATION після ліцензійно-економічного обґрунтування; не вводити його як залежність v1.

## Відкриті технічні питання
Правила збереження AI/reopen; профілі шрифтів; версія Windows/підтримка; візуальний diff PDF-AI; відповідь на timeout під час збереження; видача AI без приватних клієнтських матеріалів у Git; політика чищення output; останній реальний журнал A2 та artifact SHA.
