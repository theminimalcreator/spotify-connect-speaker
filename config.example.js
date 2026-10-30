// Arquivo de exemplo. O `install.sh` gera o web/config.js real.
//
// client_id    : app publico do Spotify. O padrao abaixo e o do ncspot, que ja
//                registra o scope "streaming" (obrigatorio para o Web Playback SDK).
//                Se voce criar seu proprio app em developer.spotify.com/dashboard,
//                troque aqui e refaca o fluxo PKCE para obter um refresh_token dele.
// refresh_token: token com scope "streaming". NUNCA versione o arquivo real.
// device_name  : nome que aparece na lista de dispositivos do Spotify.
window.CFG = {
  client_id: "d420a117a32841c2b3474932e49fb54b",
  refresh_token: "COLE_AQUI",
  device_name: "linucao",
  volume: 0.8
};
