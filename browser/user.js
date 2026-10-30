// SPDX-License-Identifier: GPL-3.0-only
// Copyright (C) 2026 Guilherme Zaia
// Preferencias do perfil dedicado do Firefox headless (copiado pelo install.sh).
// Autoplay liberado: nao ha ninguem para clicar em "Ativar audio".
user_pref("media.autoplay.default", 0);
user_pref("media.autoplay.blocking_policy", 0);
// o unico player MPRIS e o mpris.py; evita um segundo player no widget do Plasma
user_pref("media.hardwaremediakeys.enabled", false);
user_pref("media.eme.enabled", true);
user_pref("browser.shell.checkDefaultBrowser", false);
user_pref("browser.startup.homepage_override.mstone", "ignore");
user_pref("datareporting.policy.dataSubmissionEnabled", false);
user_pref("datareporting.healthreport.uploadEnabled", false);
user_pref("app.update.auto", false);
