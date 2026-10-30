# Diagnóstico: por que librespot não toca nesta conta

Registro do caminho investigativo que levou este projeto a existir. Serve para
quem chegar aqui com o mesmo sintoma não perder as mesmas horas.

## Sintoma

- Spotify Web no navegador: não tocava (mensagem pedindo para "reiniciar o dispositivo").
- `ncspot`: conectava, sincronizava biblioteca, mas nenhuma faixa tocava.
- `librespot` (CLI, modo Connect): aparecia como caixa de som, recebia o comando,
  **pulava faixa sem parar**.
- `go-librespot`: idem — 53 faixas tentadas, 51 recusadas, parou sozinho em
  "51 consecutive unplayable tracks".
- O mesmo Spotify **tocava normalmente no celular Android**, na mesma rede.

Ou seja: conta sadia, áudio da máquina funcionando (testado com `paplay` em
44,1 kHz e 48 kHz), rede e CDN ok.

## O que o log mostra

`librespot` com `-v`:

```
INFO  librespot_playback::player  Loading <Golden Touch> with Spotify URI <spotify:track:0GiN...>
DEBUG librespot_audio::fetch      Downloading file 569ddffd360ee8a283357a65d7c37086677fe005
ERROR librespot_core::audio_key   error audio key 0 1
WARN  librespot_playback::player  Unable to load key, continuing without decryption: Service unavailable { audio key error }
ERROR librespot_playback::player  Unable to read audio file: Symphonia Decoder Error: channel closed
ERROR librespot_playback::player  Skipping to next track, unable to load track <...>
```

`go-librespot` 0.10.5:

```
DEBUG selected format OGG_VORBIS_320 (410697cf9e83c95b026a7472241f2e930bb9cada)
DEBUG requested aes key for file 410697cf9e83c95b026a7472241f2e930bb9cada
WARN  skipping track: Spotify refused the audio key (code 1) for this playback context
WARN  stopping after 51 consecutive unplayable tracks
```

A leitura correta é: **o download funciona** (os arquivos chegam do CDN), o que
falta é a **chave AES** para descriptografar o OGG. O Spotify responde
`AesKeyError` com os bytes `0x00 0x01` (código 1). Sem chave, o arquivo continua
cifrado e o decoder falha — daí o silêncio e o pulo automático.

## O que foi descartado (e como)

| Hipótese | Teste | Resultado |
|---|---|---|
| Driver/placa de som | `paplay` 44,1 kHz e 48 kHz, `amixer` (amps TAS2770 on) | ❌ descartado |
| Sink padrão errado (dock USB) | era o caso inicial — corrigido | corrigido, mas o problema voltou |
| Implementação específica | `librespot` (Rust) e `go-librespot` (Go) | ❌ ambos falham |
| Bitrate / `file-id` | `-b 320`, `-b 160`, `-b 96` → `file-id` diferentes | ❌ mesmo `code 1` |
| Formato (FLAC) | `go-librespot` selecionou `OGG_VORBIS_320`, não FLAC | ❌ irrelevante |
| Conta sem Premium | `GET /v1/me` → `product: "premium"` | ❌ descartado |
| Restrição de conta | Spotify toca normal no celular Android | ❌ descartado |
| Rede / AP / CDN | `ap-gue1` (São Paulo) conecta e autentica; download ok | ❌ descartado |
| Rota dos `file-id` | `TRACK_V4` (librespot) vs `AUDIO_FILES` (go-librespot) | ❌ ambos recusados |

## A explicação dos mantenedores

[librespot#1649](https://github.com/librespot-org/librespot/issues/1649) (issue
fixada) e [#1735](https://github.com/librespot-org/librespot/issues/1735):

> "Quando o Spotify muda as coisas, ele faz em um punhado de contas de cada vez.
> Eles podem estar desativando essa forma de obter a chave, e você deu azar de
> ser um dos primeiros." — @kingosticks

> "Pelo que sabemos, não existe uma 'nova lógica de audio key' que o librespot
> possa implementar legalmente. Por ora temos que esperar e ver." — @drobotk

Investigações relacionadas: [go-librespot#235](https://github.com/devgianlu/go-librespot/issues/235)
(campo `alternative` do extended-metadata, corrigido lá em dez/2025, mas que não
resolveu este caso) e as PRs abertas em out/2026 no librespot sobre
*pace/backoff* de audio key (#1844, #1846, #1853, #1799) — todas mitigações, não
uma correção.

## Conclusão

Não é bug local e não há correção do lado do cliente: a chave é emitida pelo
servidor do Spotify e ele está negando para as contas que entraram primeiro na
migração. Escrever um cliente próprio não contorna isso — bateria na mesma porta.

O contorno é **sair do librespot** e usar o pipeline oficial:

**Web Playback SDK + Widevine no navegador.** O SDK é o mesmo caminho que os
dispositivos certificados usam; a chave vem pelo fluxo autenticado normal e a
descriptografia é feita pelo CDM. Resultado: o dispositivo aparece no Connect,
toca, e ainda ganha controles locais via MPRIS.

## Se quiser revisitar o librespot depois

Sinais de que voltou a funcionar (vale testar antes de migrar de volta, porque
librespot é bem mais leve — não precisa de navegador):

```bash
cargo install librespot --no-default-features \
  --features "native-tls,pulseaudio-backend,with-libmdns" --root ~/.local
~/.local/bin/librespot -n teste -B pulseaudio -b 160 -v 2>&1 | grep 'audio key'
```

Se não aparecer `error audio key 0 1` ao tocar uma faixa, a conta saiu do bucket
afetado.
