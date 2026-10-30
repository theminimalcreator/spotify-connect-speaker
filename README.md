# Spotify Connect Speaker (Linux / Firefox)

Transforma um PC Linux em uma **caixa de som do Spotify**: ele aparece na lista
de dispositivos do Spotify Connect (celular, tablet, outro PC) exatamente como
uma Alexa ou um Echo, mas o áudio sai pelos alto-falantes da máquina.

Nasceu de um caso real: numa conta Spotify Premium, **todas** as implementações
open-source baseadas em librespot (`ncspot`, `librespot` CLI, `go-librespot`)
eram recusadas pelo servidor com `audio key error (code 1)` — 51 faixas
consecutivas puladas, sem som. O detalhe está em
[`docs/diagnostico-librespot.md`](docs/diagnostico-librespot.md).

A solução aqui usa o caminho **oficial**: uma página com o
[Web Playback SDK](https://developer.spotify.com/documentation/web-playback-sdk)
rodando no Firefox, com a descriptografia feita pelo **Widevine**. Como é o
pipeline autenticado do próprio Spotify, o bloqueio do `audio key` não se aplica.

---

## Requisitos

| Item | Por quê |
|---|---|
| Conta **Spotify Premium** | exigência do Web Playback SDK |
| **Firefox** (ou Chromium) com **Widevine** | é quem descriptografa o áudio (EME) |
| `python3` >= 3.8 | servidor local + bridge MPRIS |
| `python3-dbus` e `python3-gobject` | teclas de mídia / widget do Plasma (opcional) |
| PipeWire ou PulseAudio | saída de áudio |

Widevine no Linux ARM64 (Asahi, Raspberry Pi, etc.):

```bash
sudo dnf install widevine-installer   # Fedora
sudo widevine-installer
```

No x86_64 o Firefox/Chromium já vêm com Widevine.

---

## Instalação

```bash
git clone <seu-repo> spotify-connect-speaker
cd spotify-connect-speaker
./install.sh
```

O `install.sh` é idempotente e faz:

1. gera `web/config.js` (client_id + refresh_token, permissão `0600`, fora do git)
2. instala os dois serviços systemd de usuário e habilita no login
3. instala o atalho no menu de aplicativos
4. valida que o servidor responde

Depois:

1. abra **http://127.0.0.1:8099** (ou o atalho *Spotify Connect*)
2. clique em **"🔊 Ativar áudio nesta aba"** — o Firefox exige um gesto do
   usuário para liberar áudio (autoplay blocking)
3. no celular: lista de dispositivos → `linucao` → play

### De onde vem o token

O Web Playback SDK precisa de um access token com o scope `streaming`.
O `scripts/gen-config.py` reaproveita o `refresh_token` que o
[ncspot](https://github.com/hrkfdn/ncspot) grava em
`~/.cache/ncspot/rspotify_token.json`, porque o app público do ncspot declara
esse scope. O token é **validado na hora** contra `accounts.spotify.com`.

Se preferir independência total, crie um app em
[developer.spotify.com/dashboard](https://developer.spotify.com/dashboard),
faça o fluxo PKCE com `streaming` nos scopes e passe:

```bash
./scripts/gen-config.py --client-id SEU_ID --refresh-token SEU_TOKEN
```

---

## Arquitetura

```
┌──────────────┐  Spotify Connect (mDNS + dealer)   ┌─────────────────────────┐
│  celular     │ ─────────────────────────────────► │  Firefox                │
│  (app oficial)│                                    │  Web Playback SDK       │
└──────────────┘                                    │  + Widevine (EME)       │
                                                    └───────────┬─────────────┘
                                                                │ áudio decodificado
┌───────────────────────────────────────────────────────────────▼─────────────┐
│ PipeWire/PulseAudio  →  alto-falantes                                        │
└──────────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────┐   HTTP 127.0.0.1:8099   ┌──────────────────────┐
│ teclas de mídia / Plasma     │ ── D-Bus MPRIS ───────► │ server.py + mpris.py │
│ (org.mpris.MediaPlayer2…)    │ ◄── estado da faixa ─── │ (ponte de comandos)  │
└──────────────────────────────┘                         └──────────────────────┘
```

| Arquivo | Papel |
|---|---|
| `web/index.html` | SDK: player, UI, atalhos de teclado, polling de comandos |
| `server.py` | serve a página (secure context) + fila de comandos + log do browser |
| `mpris.py` | exporta `org.mpris.MediaPlayer2.linucao` (teclas de mídia, widget do Plasma) |
| `scripts/gen-config.py` | gera/valida o `web/config.js` |
| `systemd/*.service.in` | units de usuário (substituídas no install) |

**Por que um servidor local e não `file://`?** O EME (Widevine) só funciona em
*secure context*. `http://127.0.0.1` conta como seguro; `file://` não.

**Como os comandos chegam na página:** ela faz `POST /state` a cada 500 ms com o
estado atual e recebe, na resposta, os comandos pendentes. O `mpris.py`
enfileira via `POST /queue`. Latência máxima de 500 ms, sem WebSocket.

---

## Controles

Na página:

| Ação | Como |
|---|---|
| Play/pause | botão central ou `Espaço` (com a aba focada) |
| Faixa seguinte / anterior | `⏭` / `⏮` ou `N` / `P` |
| Avançar/voltar 10 s | `→` / `←` |
| Buscar posição | clique na barra de progresso |
| Volume | slider ou `↑` / `↓` |

Fora da página (com a aba em segundo plano):

| Ação | Como |
|---|---|
| Play/pause, próxima, anterior | **teclas de mídia do teclado** |
| Tudo acima + capa e metadados | **widget de mídia do Plasma** / `playerctl` |

Teste rápido pela linha de comando:

```bash
gdbus call --session --dest org.mpris.MediaPlayer2.linucao \
  --object-path /org/mpris/MediaPlayer2 \
  --method org.mpris.MediaPlayer2.Player.PlayPause
```

---

## Limitações (importantes)

- **A aba precisa ficar aberta.** Fechou, o dispositivo sai da lista. Para abrir
  no login:
  ```bash
  mkdir -p ~/.config/autostart
  cp ~/.local/share/applications/spotify-connect.desktop ~/.config/autostart/
  ```
- **Todo `F5` gera um `device_id` novo.** É preciso re-selecionar o dispositivo
  no celular. É a causa número 1 de "apareceu mas ficou mudo".
- **O Firefox bloqueia áudio sem gesto do usuário.** Por isso o botão
  "Ativar áudio". Sem o clique, o Connect funciona (aparece, troca de faixa) mas
  não sai som.
- Talvez apareçam **dois players** no widget do Plasma: `Mozilla Firefox` (a
  própria integração de media keys do Firefox) e `Spotify Connect (linucao)`.
  Não quebra nada; dá para desligar a do Firefox em `about:config` com
  `media.hardwaremediakeys.enabled = false`.

---

## Diagnóstico

```bash
# a página está servindo?
curl -s http://127.0.0.1:8099/health

# o que o navegador está dizendo (a página reporta tudo aqui)
tail -f browser.log

# estado atual (é o que o bridge MPRIS lê)
curl -s http://127.0.0.1:8099/state | python3 -m json.tool

# serviços
systemctl --user status spotify-connect-web.service spotify-connect-mpris.service

# o áudio está realmente saindo?
pactl list sink-inputs | grep -A5 -i firefox
```

O painel **"Log / diagnóstico"** na página mostra `EME`, refresh de token,
`device_id`, erros do SDK e cada comando executado.

| Sintoma | Causa provável |
|---|---|
| Aparece, mas nada toca | aba sem o clique em "Ativar áudio" |
| Mudo depois de recarregar | `device_id` novo → re-selecionar no celular |
| `Widevine ausente` | rodar `widevine-installer` e reiniciar o Firefox |
| Teclas de mídia no player errado | desligar `media.hardwaremediakeys.enabled` no Firefox |

---

## Desenvolvimento

Instruções para agentes de código — e para humanos que forem mexer — estão em
[`AGENTS.md`](AGENTS.md): mapa dos arquivos, fluxo de dados, as invariantes que
não podem ser quebradas e as armadilhas conhecidas.

```bash
./scripts/check.sh   # sintaxe, cabeçalhos SPDX, segredo fora do git, saúde dos serviços
```

---

## Desinstalar

```bash
./uninstall.sh          # mantém web/config.js
./uninstall.sh --purge  # remove o refresh_token também
```

---

## Notas

- O `web/config.js` contém um segredo (refresh token) e está no `.gitignore`.
  Qualquer processo do seu usuário consegue lê-lo — é o mesmo nível de exposição
  do `~/.cache/ncspot/`. Não commite.
- Este projeto depende de um SDK proprietário da Spotify e do Widevine (DRM da
  Google). Nada de descriptografia é feito localmente: quem decodifica é o CDM.
- Se o Spotify algum dia liberar a chave AES para implementações open-source,
  `librespot` volta a ser a solução mais leve (sem navegador). Ver
  [`docs/diagnostico-librespot.md`](docs/diagnostico-librespot.md).

---

## Licença

Copyright (C) 2026 Guilherme Zaia.

Este projeto é software livre distribuído sob a **GNU General Public License,
versão 3** (`GPL-3.0-only`). O texto integral está em [`LICENSE`](LICENSE).

Em resumo:

- você pode usar, estudar, modificar e redistribuir livremente
- se **distribuir** uma versão modificada, ela tem que continuar sob GPL-3.0 e
  com o código-fonte disponível
- uso privado e uso interno **não** obrigam publicação de nada

Cada arquivo-fonte carrega a linha `SPDX-License-Identifier: GPL-3.0-only` para
que ferramentas identifiquem a licença automaticamente. Para relicenciar como
`GPL-3.0-or-later` (versão 3 ou qualquer posterior), basta trocar esse
identificador em todos os arquivos:

```bash
grep -rl 'GPL-3.0-only' --exclude-dir=.git . \
  | xargs sed -i 's/GPL-3.0-only/GPL-3.0-or-later/'
```

### Componentes de terceiros

A licença cobre **apenas o código deste repositório**. Em tempo de execução ele
usa dois componentes proprietários que **não** são distribuídos nem linkados aqui:

| Componente | Licença | Como é usado |
|---|---|---|
| [Web Playback SDK](https://developer.spotify.com/documentation/web-playback-sdk) | proprietária (Spotify) | carregado do CDN `sdk.scdn.co` pelo navegador |
| Widevine CDM | proprietária (Google) | plugin EME do próprio navegador |

Como não há linkage nem redistribuição desses binários, não há conflito de
licença. O usuário precisa de uma conta Spotify Premium e é responsável por
cumprir os Termos de Uso do Spotify ao usá-los.
