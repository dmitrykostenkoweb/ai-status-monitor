# ai-cli-status-monitor

Mini floating widget dla Linux Mint / Cinnamon pokazujący ostatni znany status Claude Code CLI i Codex CLI.

To jest lekki lokalny tool: Python 3, GTK3/PyGObject i Bash. Bez Electron, bez web servera, bez Dockera, bez network calls.

## 1. Co to jest

`ai-cli-status-monitor` używa hooków Claude Code i Codex CLI, zapisuje statusy do `~/.cache/ai-cli-status-monitor/`, a mały GTK widget czyta najświeższe wpisy i pokazuje 1-2 linie statusu.

Przykład:

```text
Claude: czyta kod [unitbox-front] 14:22
Codex: wykonuje komendę [ai-cli-status-monitor] 14:23
```

## 2. Wygląd

Widget wygląda jak mały ciemny floating card / mini-player:

- ciemne tło z delikatnym borderem i zaokrąglonymi rogami
- nagłówek: ikona radaru, `AI Agents Status`, badge stanu (`LIVE` / `N ALERT` / `IDLE`) i przycisk `×`
- jeden wiersz na aktywną sesję (do 5), każdy z: świecącą kropką w kolorze stanu, kafelkiem logo agenta, nazwą agenta, statusem (mono) i linią `projekt · czas`
- kolory zależą od stanu (myśli, czyta kod, koduje, wykonuje komendę, analizuje wynik, czeka na zgodę, zakończył)
- aktywne stany dostają animowane `...`; sesje `zakończył` są przygaszone, a nadmiar chowa stopka `+N zakończone ukryte automatycznie`
- każdy wiersz ma po prawej klikalny `przełącz →`, który aktywuje okno terminala tej sesji; wiersz `czeka na zgodę` jest dodatkowo podświetlony na czerwono z pulsującym borderem
- gdy nic nie działa: stan pusty z obracającym się radarem i `Brak aktywnych agentów`
- menu po prawym kliknięciu: `Reload`, `Open logs folder`, `Quit`

Domyślnie jest always-on-top, sticky na workspace'ach i ukryty z taskbara.

## 3. Instalacja

```bash
cd /home/dima/Documents/Personal/Projects/ai-cli-status-monitor
cp .env.default .env
# opcjonalnie: edytuj lokalny .env
./install.sh
```

Installer próbuje skonfigurować hooki automatycznie:

- Claude Code: `~/.claude/settings.json`
- Codex CLI: `~/.codex/hooks.json`
- autostart: `~/.config/autostart/ai-cli-status-widget.desktop`
- launcher w menu Cinnamon: `AI CLI Status Widget`
- launcher toggle w menu Cinnamon: `AI CLI Status Widget Toggle`
- ikona launchera: `~/.local/share/pixmaps/ai-cli-status-widget.png`
- dźwięk powiadomienia: `~/.local/share/ai-cli-status-monitor/notification.mp3`
- logo OpenAI/Codex: `~/.local/share/ai-cli-status-monitor/openai-logo.svg`
- logo Anthropic/Claude: `~/.local/share/ai-cli-status-monitor/anthropic-logo.png`
- konfiguracja runtime: `~/.config/ai-cli-status-monitor/.env`
- pozycja okna i zgodność ze starszą konfiguracją: `~/.config/ai-cli-status-monitor/widget.json`

Jeśli GTK albo `wmctrl` nie są dostępne, installer nie używa `sudo`. Wypisze komendę:

```bash
sudo apt install python3-gi gir1.2-gtk-3.0 wmctrl
```

## 4. Uruchomienie widgetu

```bash
~/.local/bin/ai-agent-status-widget
```

Demo wyglądu:

```bash
~/.local/bin/ai-agent-status-widget --demo
```

## 5. Toggle

```bash
~/.local/bin/ai-agent-status-widget-toggle
```

Po instalacji możesz też użyć wpisu w menu Cinnamon:

- `AI CLI Status Widget`
- `AI CLI Status Widget Toggle`

W menu Cinnamon możesz kliknąć wpis prawym przyciskiem i wybrać dodanie do panelu albo na pulpit.

Dodatkowo:

```bash
~/.local/bin/ai-agent-status-widget-start
~/.local/bin/ai-agent-status-widget-stop
```

## 6. Doctor

```bash
~/.local/bin/ai-agent-status-doctor
```

Sprawdza:

- skrypty w `~/.local/bin`
- cache dir
- autostart desktop file
- hooki Claude
- hooki Codex
- `wmctrl`
- import GTK
- test mode hooka

## 7. Autostart

Installer tworzy:

```text
~/.config/autostart/ai-cli-status-widget.desktop
```

Widget powinien startować automatycznie po zalogowaniu do Cinnamon.

## 7a. Konfiguracja `.env`

Publiczne wartości domyślne są w `.env.default`. Lokalny `.env` jest ignorowany przez Git. Podczas pierwszej instalacji powstaje prywatny plik `~/.config/ai-cli-status-monitor/.env` z uprawnieniami `0600`; kolejne instalacje go nie nadpisują.

Dostępne zmienne:

- `AI_STATUS_CACHE_DIR`, `AI_STATUS_CONFIG_DIR`, `AI_STATUS_DATA_DIR` — katalogi danych
- `AI_STATUS_TITLE`, `AI_STATUS_CARD_WIDTH`, `AI_STATUS_MAX_ROWS` — wygląd widgetu
- `AI_STATUS_SOUND_ENABLED` — `true`/`false`, `yes`/`no`, `on`/`off` albo `1`/`0`
- `AI_STATUS_STALE_AFTER_SECONDS`, `AI_STATUS_HIDE_DONE_AFTER_SECONDS`, `AI_STATUS_IDLE_AFTER_SECONDS`, `AI_STATUS_HIDE_STALE_AFTER_SECONDS` — timeouty
- `AI_STATUS_THEME` — nazwa motywu
- `AI_STATUS_ENV_FILE` — ścieżka do innego pliku runtime; tę zmienną trzeba wyeksportować w procesie, nie jest odczytywana z `.env`

Przykład lokalnego nadpisania:

```dotenv
AI_STATUS_TITLE="Status agentów"
AI_STATUS_MAX_ROWS=8
AI_STATUS_SOUND_ENABLED=false
```

Priorytet wartości: zmienna wyeksportowana w procesie → runtime `.env` → starsza wartość z `widget.json` → wartość wbudowana. `widget.json` nadal przechowuje pozycję okna (`x`/`y`); przy pierwszej instalacji istniejące ustawienia widgetu są przenoszone do runtime `.env`.

`.env` zapobiega przypadkowemu commitowi, ale nie szyfruje sekretów. Jeśli credential trafił do Git lub na GitHub, trzeba go unieważnić i zmienić.

Zachowanie:

- świeży status jest pokazywany normalnie
- po `stale_after_seconds` linia jest przygaszona i pokazuje `brak nowych eventów`
- po `idle_after_seconds` linia przechodzi w `idle`
- po `hide_stale_after_seconds` stary status jest ukrywany
- `zakończył` znika po `hide_done_after_seconds`, domyślnie po 3 minutach
- `czeka` włącza czerwony kolor, czerwony border/pulse i dźwięk, jeśli `sound_enabled` jest `true`

## 8. Claude Code hooks

Installer próbuje bezpiecznie zmergować hooki do:

```text
~/.claude/settings.json
```

Jeśli plik istnieje, robi backup:

```text
~/.claude/settings.json.bak.<timestamp>
```

Dodawane eventy:

- `UserPromptSubmit`
- `PreToolUse`
- `PostToolUse`
- `Notification`
- `Stop`
- `StopFailure`

Ręczny przykład jest w:

```text
examples/claude-settings-snippet.json
```

## 9. Codex CLI hooks

Installer próbuje bezpiecznie zmergować hooki do:

```text
~/.codex/hooks.json
```

Jeśli plik istnieje, robi backup:

```text
~/.codex/hooks.json.bak.<timestamp>
```

Dodawane eventy:

- `UserPromptSubmit`
- `PreToolUse`
- `PermissionRequest`
- `PostToolUse`
- `SubagentStop`
- `Stop`

Dla Codex CLI może być nadal potrzebne wejście w `/hooks` i zatwierdzenie hooków.

Ręczny przykład jest w:

```text
examples/codex-hooks.json
```

## 10. Troubleshooting

Uruchom doctor:

```bash
~/.local/bin/ai-agent-status-doctor
```

Sprawdź panelowy output:

```bash
~/.local/bin/ai-agent-status-panel
```

Sprawdź pliki:

```bash
ls -la ~/.cache/ai-cli-status-monitor/
ls -la ~/.cache/ai-cli-status-monitor/last_payloads/
ls -la ~/.cache/ai-cli-status-monitor/debug_payloads/
cat ~/.cache/ai-cli-status-monitor/widget.log
```

Test hooków:

```bash
~/.local/bin/ai-agent-status-hook --agent claude --test
~/.local/bin/ai-agent-status-hook --agent codex --test
```

Jeśli Codex nie odpala hooków, wejdź w `/hooks` i zatwierdź/zaufaj nowym hookom.

Przy wielu uruchomionych konsolach statusy są trzymane osobno w:

```text
~/.cache/ai-cli-status-monitor/statuses/
```

Pliki `claude.json` i `codex.json` nadal wskazują ostatni status danego agenta dla kompatybilności ze starszymi skryptami.

Widget odtwarza `notification.mp3` tylko przy wejściu w stan wymagający Twojej interakcji, np. czeka na zgodę albo czeka na odpowiedź. Jeśli nie słychać dźwięku, sprawdź `~/.cache/ai-cli-status-monitor/widget.log`; widget używa dostępnego lokalnego odtwarzacza, np. `mpv`, `ffplay`, `mpg123`, `gst-play-1.0` albo `paplay`.

Jeśli widget nie jest nad wszystkimi oknami, sprawdź:

```bash
command -v wmctrl
```

## 11. Limitations

- Status jest event-based, nie jest prawdziwym podglądem “myśli modelu”.
- Status `myśli` jest inferowany po promptach i tool eventach.
- Status `czeka na Ciebie` zależy od dostępnych notification, stop i permission eventów.
- Always-on-top i all-workspaces najlepiej działa na X11/Cinnamon.
- Wayland może ograniczać sticky/above/skip-taskbar behavior.
- Każda sesja AI ma osobny wiersz. Tożsamość sesji bierze się z `session_id` (Claude), a gdy go brak (Codex) — z lidera sesji POSIX (shell terminala), więc jedna sesja = jeden stabilny wiersz, nawet bez `session_id`.
- `przełącz →` dopasowuje okno po PID procesu terminala, a gdy jeden proces emulatora obsługuje wiele okien (np. gnome-terminal), rozróżnia je po tytule okna. Pełną pewność daje terminal jeden-proces-na-okno (alacritty, kitty, xterm); konkretnej karty (tab) `wmctrl` nie przełączy. Wymaga `wmctrl`/X11; pod Wayland, tmux, screen lub ssh może nie trafić w okno. Wpis diagnostyczny ląduje w `widget.log`.
