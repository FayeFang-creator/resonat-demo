# Data License and Attribution

The code and documentation in this repository are licensed under the MIT License
(see LICENSE). This notice covers the contents of the `data/` folder and any audio
referenced from it, which are **not** covered by the MIT License.

## Music and metadata (Jamendo / JamendoMaxCaps)

The track catalog, track metadata (titles, artists, durations), and audio referenced
in this repository are derived from the **Jamendo** platform, via the
**JamendoMaxCaps** dataset (AMAAI Lab), available at
https://huggingface.co/datasets/amaai-lab/JamendoMaxCaps and licensed under
**Creative Commons Attribution-ShareAlike 3.0 (CC BY-SA 3.0)**.

- Individual tracks are released by their artists under their own Creative Commons
  licenses. Some carry additional conditions (for example, non-commercial or
  no-derivatives terms).
- You must respect the attribution requirements and the per-track license terms for
  any track you use.
- Audio download links point to Jamendo's public content servers. The audio is the
  property of the respective artists and rights holders.

Attribution: music and metadata courtesy of Jamendo (https://www.jamendo.com) and the
JamendoMaxCaps dataset (AMAAI Lab).

## Demo catalog (`backend/data/demo_catalog.json`)

赛后 Cyanite API 下线，检索改用这份本地曲库。它由 `backend/build_catalog.py` 从
**Jamendo 公开 API** 抓取，只含曲目元数据（id、曲名、艺术家、时长、标签、许可链接），
适用与上面相同的 CC BY-SA 3.0 / 每曲各自的 Creative Commons 条款。
**不含任何 Cyanite 模型输出。**

## Cyanite analysis

Audio analysis, tags, scores, and model outputs produced by Cyanite for these tracks
are the intellectual property of Cyanite (elceedee UG, haftungsbeschränkt) and are
governed by the Cyanite Sponsor Challenge Agreement, not by this notice.

## User profiles (pseudonymized)

The user profiles in `data/` (user identifiers and their associated liked tracks) are
**pseudonymized**: they contain numeric identifiers only, with no names, emails, or
other directly identifying information.

This data is provided solely for participation in HACKATUNE 2026. By using it you agree
to:

- process it only for the purpose of the Cyanite challenge at HACKATUNE 2026,
- not attempt to re-identify any individual, or combine it with other sources to do so,
- not retain or further distribute it beyond what is necessary for the event,
- and comply with applicable data protection law, including the GDPR.

## Summary

| Item | Terms |
|---|---|
| Repository code and docs | MIT License (see LICENSE) |
| Track audio and metadata | Creative Commons (Jamendo / JamendoMaxCaps, CC BY-SA 3.0; per-track licenses apply) |
| Cyanite tags and analysis | Cyanite IP, per the Sponsor Challenge Agreement |
| User profiles | Pseudonymized, HACKATUNE 2026 use only, GDPR applies |
