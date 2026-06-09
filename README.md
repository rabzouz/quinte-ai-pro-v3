# Quinté AI Pro V3

Application HTML autonome pour préparer des pronostics Quinté+ avec récupération de données, analyse IA, scoring multicritère, méthode technique, simulation Monte Carlo, value bets, paris conseillés et comparaison avec le résultat officiel.

## Fonctionnalités

- Récupération automatique enrichie des partants, cotes, profils, météo et statistiques.
- Sources complémentaires PMU/turf intégrées dans les prompts IA.
- Support OpenAI et Anthropic.
- Proxy OpenAI optionnel pour Android/WebView ou blocages CORS.
- Méthode technique : piste-distance, musique, engagement, driver, ferrage, météo, risques et value.
- Monte Carlo 100 000 simulations.
- Poisson, fusion, pronostics et tickets PMU.
- Onglet Résultat pour comparer l'arrivée officielle au classement de l'app.

## Fichiers

- `index.html` : application complète.
- `quinte_engine.py` : moteur Python avancé pour calculer classement, probabilités, value bets et tickets.
- `examples/sample_race.json` : exemple de données pour tester le moteur Python.
- `cloudflare-worker/openai_proxy_cloudflare_worker.js` : proxy Cloudflare Worker pour OpenAI.
- `cloudflare-worker/openai_proxy_cloudflare_worker.mjs` : même proxy en module ES pour validation locale.

## Utilisation locale

Ouvrez directement `index.html` dans un navigateur.

Sur Android/WebView, l'appel direct vers OpenAI peut être bloqué. Dans ce cas :

1. Déployez le Worker Cloudflare fourni.
2. Copiez l'URL publique du Worker, par exemple `https://nom-du-worker.compte.workers.dev`.
3. Collez cette URL dans le champ `Proxy OpenAI`.
4. Cliquez sur `Proxy`.
5. Collez votre clé OpenAI dans le champ API, puis cliquez `Sauver`.

## Moteur Python de pronostic

Le moteur Python fonctionne sans dépendance externe.

Exemple :

```powershell
python quinte_engine.py examples/sample_race.json --runs 50000 --pretty
```

Sortie JSON complète :

```powershell
python quinte_engine.py examples/sample_race.json --runs 100000
```

Le moteur combine :

- score presse/forme/terrain/musique
- probabilité implicite des cotes
- driver/jockey et consensus presse
- météo et méthode technique
- pénalités de risque
- détection value bet
- simulation pondérée de type Plackett-Luce
- génération de tickets Quinté ordre/désordre, champ réduit, Quarté et Tiercé

## Déployer le proxy Cloudflare Worker

1. Ouvrez Cloudflare Dashboard.
2. Allez dans `Workers & Pages`.
3. Créez un Worker.
4. Collez le contenu de `cloudflare-worker/openai_proxy_cloudflare_worker.js`.
5. Déployez.
6. Utilisez l'URL `https://...workers.dev` dans l'application.

## Sécurité

Ne committez jamais de clé API. L'application stocke la clé côté navigateur uniquement, dans `localStorage` quand disponible, avec fallback mémoire pour Android/WebView.

## Sources intégrées

L'application transmet aux prompts IA des sources comme PMU, Paris-Turf, Geny, Canalturf, Turfomania, OutilTurfiste, Turfoo, Zone-Turf, LeTROT, France Galop, ZEturf, Open PMU API et Aspiturf.

## Avertissement

Cette application est une aide à la décision. Les pronostics ne garantissent aucun gain. Jouez avec modération.
