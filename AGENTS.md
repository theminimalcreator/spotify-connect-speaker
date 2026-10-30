# AGENTS.md

Instruções para agentes de código (pi, Claude Code, Cursor, Codex) trabalhando
neste repositório. Leia antes de propor mudanças.

## O que é este projeto

Transforma um PC Linux em uma **caixa de som do Spotify Connect** (aparece na
lista de dispositivos do celular como uma Alexa). O áudio sai por uma página com
o **Web Playback SDK** aberta no Firefox, descriptografada pelo **Widevine**.

Não é uma lib nem um serviço de longa duração: é um servidor HTTP local
(127.0.0.1:8099) que serve uma página, mais uma ponte D-Bus/MPRIS para as teclas
de mídia. O "player" real é o navegador.

## Decisão de arquitetura — não desfaça

**Não reintroduza librespot, ncspot, go-librespot, spotifyd ou qualquer cliente
baseado em librespot.** A motivação está em
[`docs/diagnostico-librespot.md`](docs/diagnostico-librespot.md): em contas
atingidas por um rollout do Spotify, o servidor recusa a chave AES
(`error audio key 0 1`) e **toda** faixa é pulada sem som — reproduzido em duas
implementações independentes (Rust e Go), em três bitrates, com `file-id`
diferentes. Não é bug local e não há correção client-side.

O Web Playback SDK funciona porque usa o pipeline autenticado oficial. Qualquer
sugestão de "usar librespot que é mais leve" está errada **para este caso** e já
foi descartada com evidências.

Também não tente implementar descriptografia local: quem decodifica é o CDM
(Widevine) dentro do navegador. Não há chave para extrair.

## Mapa dos arquivos

| Arquivo | Papel | Restrições |
|---|---|---|
| `web/index.html` | SDK do Spotify, UI, teclado, polling de comandos | arquivo único, sem build, sem bundler |
| `server.py` | serve `web/`, fila de comandos, log do browser | **só stdlib** |
| `mpris.py` | exporta `org.mpris.MediaPlayer2.<device>` | `python3-dbus` + `PyGObject` (pacotes do sistema) |
| `scripts/gen-config.py` | gera/valida `web/config.js` | só stdlib |
| `scripts/check.sh` | verificação do repo (sintaxe, SPDX, segredo, saúde) | sai 0 só se tudo passar |
| `install.sh` / `uninstall.sh` | instala/remove units + atalho | idempotentes |
| `systemd/*.service.in` | templates com `@APPDIR@` | substituído pelo `install.sh` |
| `desktop/*.desktop.in` | atalho no menu | `@URL@`, `@NAME@` |
| `web/config.js` | **SEGREDO** (client_id + refresh_token) | 0600, gitignored, nunca imprimir |

## Fluxo de dados

```
celular --Spotify Connect--> Firefox (SDK + Widevine) --> PipeWire --> alto-falantes
                                   |
                                   | POST /state  (a cada 500 ms, carrega o estado
                                   |               e recebe {"commands": [...]})
                                   v
                            server.py (127.0.0.1:8099)
                                   ^
                                   | POST /queue
                                   |
              mpris.py (D-Bus) <-- teclas de mídia / widget do Plasma
```

Superfície HTTP:

| Rota | Efeito |
|---|---|
| `GET /` | `web/index.html` |
| `GET /health` | `{"ok": true, "port": 8099}` |
| `GET /state` | último estado (lido pelo `mpris.py`) |
| `POST /state` | atualiza estado e devolve `{"commands": [...]}` |
| `POST /queue` | enfileira comando (máx. 20) |
| `POST /log` | log do navegador → `browser.log` |

Campos do estado: `connected`, `playing`, `title`, `artist`, `album`, `art`,
`position`, `duration`, `volume`, `updated`.

Comandos aceitos (string simples): `playpause`, `play`, `pause`, `next`,
`previous`, `seek_rel:<ms>`, `seek_abs:<ms>`, `volume:<0-100>`.

## Invariantes — quebrar alguma destas quebra o produto

1. **Servir em `http://127.0.0.1:<porta>`, nunca `file://`.** EME/Widevine exige
   *secure context*; `localhost` conta como seguro, `file://` não.
2. **O polling de 500 ms é o contrato de comandos.** Não troque por WebSocket
   sem necessidade: latência de 500 ms é aceitável e elimina estado de conexão.
3. **O `device_id` do SDK muda a cada carregamento da página.** É a causa nº 1
   de "apareceu mas ficou mudo": depois de um F5 é preciso re-selecionar o
   dispositivo no celular. Não tente persistir/forjar `device_id`.
4. **Autoplay exige gesto do usuário.** O botão "Ativar áudio" chama
   `player.activateElement()`. Se você remover esse botão, o dispositivo aparece,
   recebe comandos, troca de faixa — e não sai som nenhum.
5. **A aba precisa ficar aberta.** Fechou, o dispositivo sai da lista do Spotify.
6. **`web/config.js` nunca entra no git.** Contém refresh token. O `.gitignore`
   cobre; não use `git add -f`.
7. **`python3` só stdlib em `server.py` e nos scripts.** `mpris.py` pode usar
   `dbus` e `gi` porque são pacotes de sistema já exigidos.

## Rodar e verificar

```bash
./install.sh                               # instala/atualiza units + atalho + config
systemctl --user status spotify-connect-web spotify-connect-mpris
curl -s http://127.0.0.1:8099/health
curl -s http://127.0.0.1:8099/state | python3 -m json.tool
tail -f browser.log                        # log do navegador (a página reporta tudo)

# controle local, sem tocar no navegador
gdbus call --session --dest org.mpris.MediaPlayer2.linucao \
  --object-path /org/mpris/MediaPlayer2 \
  --method org.mpris.MediaPlayer2.Player.PlayPause

# o áudio está realmente saindo?
pactl list sink-inputs | grep -A5 -i firefox
```

**Antes de terminar qualquer mudança, rode:**

```bash
./scripts/check.sh
```

Cobre sintaxe (python, bash, o `<script>` inline do HTML), presença dos
cabeçalhos SPDX, que `web/config.js` não está no índice do git e — se os
serviços estiverem no ar — `/health`, `GET /` e a resposta do D-Bus. Sai 0 só se
tudo passar; `skip` é aceitável (ex.: `node` ou serviços ausentes).

Se mexeu no `mpris.py`, reinicie `spotify-connect-mpris` e confirme que
`GetAll` responde:

```bash
gdbus call --session --dest org.mpris.MediaPlayer2.linucao \
  --object-path /org/mpris/MediaPlayer2 \
  --method org.freedesktop.DBus.Properties.GetAll \
  org.mpris.MediaPlayer2.Player
```

## Convenções de código

- Comentários, UI, mensagens de log e documentação em **português do Brasil**;
  identificadores e nomes de API em inglês.
- `web/index.html` é intencionalmente um arquivo só (HTML + CSS + JS inline),
  sem dependências de build. Não introduza bundler, npm ou framework.
- UI sem libs: DOM direto, `fetch`, CSS puro. Tema escuro, fundo `#121212`.
- Escrita de estado sempre sob o `LOCK` do `server.py`.
- Units systemd são de **usuário** (`--user`), nunca de sistema.
- Cabeçalho `SPDX-License-Identifier: GPL-3.0-only` obrigatório em arquivo novo.
- Commits em português, modo imperativo, com o "porquê" no corpo quando não for
  óbvio.

## Ambiente de referência

Fedora Asahi Remix 44, aarch64 (MacBook Air M2), KDE Plasma em X11, PipeWire
1.6.8, Firefox 155. Widevine em `/var/lib/widevine` (instalado via
`sudo widevine-installer`), exposto ao Firefox por `MOZ_GMP_PATH`. Se o log da
página disser `Widevine ausente`, o CDM não está instalado ou o Firefox precisa
ser reiniciado.

## Armadilhas conhecidas

| Sintoma | Causa |
|---|---|
| Aparece na lista, nada toca | falta o clique em "Ativar áudio" (autoplay) |
| Mudo depois de recarregar | `device_id` novo; re-selecionar no celular |
| Dois players no widget do Plasma | `media.hardwaremediakeys.enabled` do Firefox ligado |
| `GET /` 200 mas página em branco | abriu via `file://` em vez de `127.0.0.1` |
| Comando pela tecla não chega | `spotify-connect-mpris` parado, ou `mpris.py` sem `dbus` |
| `install.sh` falha no meio | units apontam para caminho antigo: rodar `install.sh` de novo após mover o repo |

## Fora de escopo

Não implemente sem pedido explícito: empacotamento (RPM/Flatpak/AUR), suporte a
Chromium além do que já funciona, autenticação multiusuário, TLS, ou qualquer
coisa que dependa de credenciais Spotify embutidas no código.
