#!/usr/bin/env python3
"""Build the national funnel, regional tables, indicator assessment, and report."""
from __future__ import annotations

import datetime as dt
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from common import ANALYSIS, RAW, links_dataset_files, read_csv, write_csv

PREFS = ["北海道","青森県","岩手県","宮城県","秋田県","山形県","福島県","茨城県","栃木県","群馬県","埼玉県","千葉県","東京都","神奈川県","新潟県","富山県","石川県","福井県","山梨県","長野県","岐阜県","静岡県","愛知県","三重県","滋賀県","京都府","大阪府","兵庫県","奈良県","和歌山県","鳥取県","島根県","岡山県","広島県","山口県","徳島県","香川県","愛媛県","高知県","福岡県","佐賀県","長崎県","熊本県","大分県","宮崎県","鹿児島県","沖縄県"]


def truth(value: object) -> bool:
    return str(value).strip().lower() in ("true", "1", "yes", "y")


def write_report(gtfs, match_rows, link_ready, transport_count, overview_count, driver_count, hist2_count, hist3_count, full_count, gtfs_hist2_total, gtfs_hist3_total, prefecture_rows, ehime_rows, indicators, links_status, gtfs_source_status):
    gtfs_n = len(gtfs)
    if links_status:
        matched_n = len(match_rows)
        matched_text = str(matched_n)
        transport_text, overview_text, driver_text = map(str, (transport_count, overview_count, driver_count))
        hist2_funnel_text, hist3_funnel_text, full_text = map(str, (hist2_count, hist3_count, full_count))
    else:
        matched_n = None
        matched_text = "NOT ESTABLISHED (0 confirmed in this run; true count unknown)"
        transport_text = overview_text = driver_text = "NOT EVALUABLE (0 confirmed in retrieved rows; true count unknown)"
        hist2_funnel_text = hist3_funnel_text = full_text = "NOT EVALUABLE with LINKS (0 confirmed; true count unknown)"
    hist2_text, hist3_text = str(gtfs_hist2_total), str(gtfs_hist3_total)
    lines = [
        f"GTFS bus operator entities (agency-derived; legal count unverified): {gtfs_n}",
        f"LINKS matched: {matched_text}",
        f"Transport performance complete: {transport_text}",
        f"Business overview complete: {overview_text}",
        f"Driver count complete: {driver_text}",
        f"2+ years GTFS history (GTFS-only, all component feeds): {hist2_text}",
        f"3+ years GTFS history (GTFS-only, all component feeds): {hist3_text}",
        f"Funnel 6 after LINKS + driver data (2+ years): {hist2_funnel_text}",
        f"Funnel 7 after LINKS + driver data (3+ years): {hist3_funnel_text}",
        f"Full Supply Stress Test eligible: {full_text}",
        "",
        "# Final assessment — Transit Supply Stress Test",
        "",
        "## 1. 結論",
    ]
    if links_status:
        lines += [f"- 今回取得した全国GTFSから、バス路線を持つ内部 agency_name の正規化事業者エンティティは **{gtfs_n}** 件。",
                  f"- LINKSとの照合は **{matched_n}** 件が Match A/B/C として確認済み。輸送実績・概況・運転者を揃える事業者は **{full_count}** 件（3年以上のGTFS履歴を含む厳格定義）。",
                  f"- GTFS履歴単独では2年以上 **{gtfs_hist2_total}** 件、3年以上 **{gtfs_hist3_total}** 件（各構成feedすべてで確認）。",
                  "- 判定は、実測した完全データ件数と欠損分布で行う。推計値やGTFSフィード数は事業者数に転用していない。"]
    else:
        lines += ["- LINKSの2025年度データ本体は本実行環境から取得できず、LINKS側の事業者名・列・レコードを一件も実査できていない。したがって照合数、輸送実績充足数、概況充足数、運転者数充足数、最終完全充足数は**未確定**であり、0社と断定していない。",
                  f"- GTFSは公式APIから取得・解析できた範囲で、バスの内部agencyを事業者エンティティとして **{gtfs_n}** 件確認した。これは道路運送法上の法人事業者数ではない。LINKSの未取得により本命案の中心仮説は検証未完了。",
                  f"- GTFS履歴単独は、全構成feedベースで2年以上 **{gtfs_hist2_total}** 件、3年以上 **{gtfs_hist3_total}** 件を実測。LINKS・運転者データを加えたFunnel 6/7は未確定。",
                  "- 採用判定はこの証拠状態では **FAIL（本命採用を見送る）**。これはLINKSデータに欠損があると実測した結論ではなく、必要な公式データ本体を取得できず、全国版の実現性を立証できなかったことによる保守判定。"]
    lines += ["", "## 2. データ取得結果", "",
              f"- GTFS公式API: {gtfs_source_status}",
              "- GTFS現行有効性: 2026-09-29を基準日とし、取得したZIP内 `feed_info.txt` の有効期間を優先。公式レジストリの日付だけでは選別していない。選択feed数、agency行数、entity数は別に保持。",
              f"- LINKS: {links_status}",
              "- 取得URL/statusと応答、取得日時、SHA256は `data/raw/source_manifest.csv`、`data/raw/links/fetch_status.json`、`data/raw/gtfs_download_manifest.csv` に記録。",
              "- LINKS取得試行: CKAN package_show API、公式データセットページ、公開resource URLへのcurl GET、Chrome相当User-Agent/MLIT Referer/CSV・ZIP Acceptヘッダーを試行。CKAN API・ページ・resource URLはいずれも403（alternate hostは502）。Python `requests` / `httpx` は未導入（ModuleNotFoundError）。認証・WAF回避は行っていない。",
              "", "## 3. 名寄せ結果", "",
              "- GTFS側は必ず `agency.txt` の `agency_name` を主名としている。publisher / organization_name は出所情報として残し、道路運送事業者と同一視していない。",
              "- agency_nameは法人事業者名とは限らない。実測上、市/区/町/村で終わる名称と協議会の文字列シグナルが多く、運行受託者はLINKS照合前には不明。",
              "- Match A=raw完全一致、B=NFKC・空白・法人格除去後一致、C=根拠と所在地検証を含む承認済み別名、D=fuzzy候補（未確定）、E=比較済みで候補なし。",
              "- LINKS本体未取得時は全GTFS事業者をEに割り当てず、`not_evaluable` として扱う。実際の表は `match_summary.csv` / `unmatched_gtfs.csv`。",
              "", "## 4. 必要項目充足率", "",
              "- LINKS CSVの実列を取得できていないため、事業者名、許可区分、輸送人員、車両数、営業収入、所在地、年度、運転者数の存在・非欠損率は未確定。列名をユースケースの説明やGitHubのテストコードから補っていない。",
              "- 列ごとの取得可否・行数・年度別非欠損数は `field_completeness.csv`。未取得は空欄 / not_evaluable とし0扱いしていない。",
              "- 公式LINKSユースケース紹介ページは、2022–2024の輸送実績と2023–2024の概況・運転者関連のレコード例・集計を説明しているが、当該説明値は本調査のoperator-level集計には流用していない。",
              "", "## 5. GTFS履歴", "",
              "- 公式APIの `rid=prev_N` で過去ZIPを取得し、ZIP数ではなく `routes/trips/stop_times` と週次・例外サービス定義からschedule generationを識別。`feed_info`/agency等のみの変更、同一時刻表の再アップロード、calendar有効期間だけの延長を別分類。",
              "- 事業者の2年/3年履歴は、複数フィードを持つ事業者の場合、構成する全現行feedが必要期間を満たす場合にのみ充足とする。詳細は `gtfs_history_summary.csv` と `gtfs_history_versions.csv`。",
              "", "## 6. 都道府県別結果", "",
              "- 47都道府県別GTFS agency entity数は公式feedの `feed_pref_id` を使用。停留所座標から運行域を逆ジオコードした結果ではない。match数・完全充足数はLINKS取得不能のため未評価。複数県にまたがるagencyは県別合計が全国ユニーク数と一致しない。",
              "", "## 7. 愛媛県詳細", "",
              "- 県別表と `ehime_detail.csv` に、GTFSの `agency_name`、publisher、feed、routes/trips/stops、供給proxy、LINKS有無、履歴を記録。伊予鉄バス等の照合はLINKS名簿未取得のため未確定。",
              "", "## 8. Supply Stress Testで計算可能な指標", "",
              "- GTFS側の運行便数はcalendar/calendar_datesを適用した平均日次便数。trip-hoursはstop_timesの始終点所要時間を全tripで合算した値で、車両勤務時間ではない。距離は停留所座標間の大円距離合計で、道路経路長ではない。",
              "- A–Jの可否・実測件数と必要列・年度・名寄せ条件は `indicator_feasibility.csv`。代理量は代理量と明記し、欠けたLINKS値を推計・0置換していない。",
              "", "## 9. 最大のデータ制約", "",
              "- 公式LINKS資源の公開ページは検索インデックスで見つかったが、CKAN API・resource URLとも取得時HTTP 403（CloudFront ‘Request blocked’）。データ仕様書とCSV本体を読めていないため、列・粒度・実事業者coverageを検証できない。",
              "- この制約が解消するまで、「driver count exists at operator/year grain」「operator count with all required data」「national complete funnel」は未確定。",
              "", "## 10. PASS / CONDITIONAL PASS / FAIL", "",
              ("**CONDITIONAL PASS** — 完全充足事業者が複数地域で十分確認でき、取得・名寄せ手順を再現できた場合。現在の数値での判定ではありません。" if links_status and full_count >= 20 else "**FAIL（現時点の本命採用判断）** — LINKS実ファイルの取得と事業者レベル照合が未成立で、必須の全国充足件数を証拠で示せない。LINKS data access restored後に再実行すれば判定が変わり得るが、現状をPASSとはしない。"),
              "",
              "### 再現・制約",
              "",
              "`python scripts/fetch_gtfs_registry.py` → `python scripts/fetch_gtfs.py --mode current` → `python scripts/analyze_gtfs.py` → `python scripts/fetch_gtfs.py --mode history --history-depth 12 --ids-file data/processed/gtfs_bus_feed_ids.txt` → `python scripts/analyze_history.py` → `python scripts/analyze_links_fields.py` → `python scripts/match_operators.py` → `python scripts/build_funnel.py`。",
              "- 実測日は2026-09-29（日本時間基準）。各取得時刻はUTCでmanifestに記録。",
              "- GTFS APIとLINKS APIは将来更新されるため、再実行時はAPIの現行応答が正。"]
    (ANALYSIS / "final_assessment.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    gtfs = read_csv(ANALYSIS / "gtfs_operator_metrics.csv") if (ANALYSIS / "gtfs_operator_metrics.csv").exists() else []
    matches = read_csv(ANALYSIS / "matched_operators.csv") if (ANALYSIS / "matched_operators.csv").exists() else []
    gtfs_hist = read_csv(ANALYSIS / "gtfs_history_summary.csv") if (ANALYSIS / "gtfs_history_summary.csv").exists() else []
    hist_by_id = {x.get("operator_id"): x for x in gtfs_hist}
    link_rows = read_csv(ANALYSIS / "links_operator_metrics.csv") if (ANALYSIS / "links_operator_metrics.csv").exists() else []
    raw_links = read_csv(ANALYSIS / "links_raw_rows.csv") if (ANALYSIS / "links_raw_rows.csv").exists() else []
    links_acquired = bool(links_dataset_files())
    link_by_id = {x.get("links_operator_id"): x for x in link_rows}
    match_by_gtfs = {x.get("operator_id"): x for x in matches}
    history_by_id = hist_by_id

    link_keys: dict[str, dict[str, set[tuple[str, str]]]] = defaultdict(lambda: defaultdict(set))
    transport_rows_by_key: dict[tuple[str, str, str], list[dict[str, bool]]] = defaultdict(list)
    for row in raw_links:
        lid, year = row.get("links_operator_id", ""), row.get("year", "")
        if not lid or not year:
            continue
        ds = row.get("dataset", "")
        permit = row.get("permit_type", "").strip()
        if ds in ("transport_performance", "business_overview"):
            link_keys[lid][ds].add((year, permit))
        if ds == "transport_performance":
            key = (lid, year, permit)
            transport_rows_by_key[key].append({
                metric: bool(row.get(metric, "").strip("| "))
                for metric in ("passenger_count", "vehicle_count", "revenue", "driver_count")
            })
        elif ds == "business_overview":
            pass

    per_gtfs = {}
    for op in gtfs:
        gid = op.get("operator_id", "")
        m = match_by_gtfs.get(gid)
        link_id = m.get("links_operator_id") if m else ""
        common_pairs = sorted(link_keys[link_id].get("transport_performance", set()) & link_keys[link_id].get("business_overview", set()), reverse=True) if link_id else []
        selected_pair = common_pairs[0] if common_pairs else ("", "")
        year, permit_type = selected_pair
        row_values = transport_rows_by_key.get((link_id, year, permit_type), []) if link_id and year else []
        transport_complete = any(all(r.get(k, False) for k in ("passenger_count", "vehicle_count", "revenue")) for r in row_values)
        overview_complete = bool(year and selected_pair in link_keys[link_id].get("business_overview", set()))
        driver_complete = any(all(r.get(k, False) for k in ("passenger_count", "vehicle_count", "revenue", "driver_count")) for r in row_values)
        h = history_by_id.get(gid, {})
        h2, h3 = truth(h.get("2plus_year_all_feeds")), truth(h.get("3plus_year_all_feeds"))
        per_gtfs[gid] = {"links_operator_id": link_id, "common_year": year, "common_permit_type": permit_type, "transport_complete": transport_complete, "overview_complete": overview_complete, "driver_complete": driver_complete, "history_2plus": h2, "history_3plus": h3}

    operator_detail = []
    for op in gtfs:
        gid = op.get("operator_id", "")
        m = match_by_gtfs.get(gid, {})
        v = per_gtfs.get(gid, {})
        h = history_by_id.get(gid, {})
        operator_detail.append({**op,
            "match_class": m.get("match_class", "not_evaluable" if not links_acquired else "E"),
            "links_operator_id": m.get("links_operator_id", ""), "links_operator_name": m.get("links_operator_name", ""),
            "common_links_year": v.get("common_year", "unknown" if not links_acquired else ""),
            "common_permit_type": v.get("common_permit_type", "unknown" if not links_acquired else ""),
            "transport_performance_complete": "unknown" if not links_acquired else v.get("transport_complete", False),
            "business_overview_present": "unknown" if not links_acquired else v.get("overview_complete", False),
            "driver_count_complete": "unknown" if not links_acquired else v.get("driver_complete", False),
            "gtfs_2plus_year_history": h.get("2plus_year_all_feeds", ""), "gtfs_3plus_year_history": h.get("3plus_year_all_feeds", ""),
            "drop_reason": "LINKS source unavailable; match and LINKS field status unknown" if not links_acquired else ""})
    write_csv(ANALYSIS / "operator_funnel_detail.csv", operator_detail)

    # Funnel counts are only computed when source rows were obtained.
    if links_acquired:
        matched_n = len(matches)
        transport_n = sum(x["transport_complete"] for x in per_gtfs.values())
        overview_n = sum(x["transport_complete"] and x["overview_complete"] for x in per_gtfs.values())
        driver_n = sum(x["transport_complete"] and x["overview_complete"] and x["driver_complete"] for x in per_gtfs.values())
        hist2_n = sum(x["transport_complete"] and x["overview_complete"] and x["driver_complete"] and x["history_2plus"] for x in per_gtfs.values())
        hist3_n = sum(x["transport_complete"] and x["overview_complete"] and x["driver_complete"] and x["history_3plus"] for x in per_gtfs.values())
        full_n = hist3_n
        funnel = [
            ("Funnel 1 GTFS bus operator entities", len(gtfs), "measured"),
            ("Funnel 2 LINKS matched A/B/C", matched_n, "measured"),
            ("Funnel 3 transport passenger+vehicle+revenue", transport_n, "measured_conservative_same_year"),
            ("Funnel 4 plus business overview", overview_n, "measured_conservative_same_year"),
            ("Funnel 5 plus driver count", driver_n, "measured_conservative_same_year"),
            ("Funnel 6 plus 2+ year GTFS history", hist2_n, "measured_all_component_feeds"),
            ("Funnel 7 plus 3+ year GTFS history", hist3_n, "measured_all_component_feeds"),
        ]
    else:
        matched_n = transport_n = overview_n = driver_n = hist2_n = hist3_n = full_n = None
        funnel = [("Funnel 1 GTFS bus operator entities", len(gtfs), "measured"), ("Funnel 2 LINKS matched A/B/C", "", "not_evaluable_LINKS_source_unavailable"), ("Funnel 3 transport performance complete", "", "not_evaluable_LINKS_source_unavailable"), ("Funnel 4 plus business overview", "", "not_evaluable_LINKS_source_unavailable"), ("Funnel 5 plus driver count", "", "not_evaluable_LINKS_source_unavailable"), ("Funnel 6 plus 2+ year GTFS history", "", "not_evaluable_LINKS_source_unavailable"), ("Funnel 7 plus 3+ year GTFS history", "", "not_evaluable_LINKS_source_unavailable")]
    write_csv(ANALYSIS / "funnel_summary.csv", [{"stage": stage, "operator_count": value, "status": status} for stage, value, status in funnel])

    # Regional counts are agency-entity counts; multi-prefecture operators are
    # counted in every represented prefecture and national totals stay unique.
    prefecture_rows = []
    for pref in PREFS + ["全国・都道府県不明"]:
        ops = [x for x in gtfs if pref in x.get("prefectures", "").split("|")] if pref != "全国・都道府県不明" else [x for x in gtfs if "不明" in x.get("prefectures", "") or "全国" in x.get("prefectures", "")]
        n_match = sum(bool(match_by_gtfs.get(x.get("operator_id")) and match_by_gtfs[x.get("operator_id")].get("match_class") in ("A", "B", "C")) for x in ops) if links_acquired else ""
        n_full = sum(bool(per_gtfs.get(x.get("operator_id"), {}).get("history_3plus") and per_gtfs.get(x.get("operator_id"), {}).get("driver_complete") and per_gtfs.get(x.get("operator_id"), {}).get("transport_complete") and per_gtfs.get(x.get("operator_id"), {}).get("overview_complete")) for x in ops) if links_acquired else ""
        prefecture_rows.append({"prefecture": pref, "gtfs_bus_operator_entities": len(ops), "links_matched_A_B_C": n_match, "full_complete_supply_stress_test": n_full, "coverage_rate": (round(n_full / len(ops), 4) if links_acquired and ops else (0 if links_acquired else "")), "links_status": "measured" if links_acquired else "not_evaluable_LINKS_source_unavailable"})
    write_csv(ANALYSIS / "prefecture_summary.csv", prefecture_rows)

    ehime = [x for x in gtfs if "愛媛県" in x.get("prefectures", "")]
    ehime_rows = []
    for op in ehime:
        gid = op.get("operator_id")
        m = match_by_gtfs.get(gid, {})
        h = history_by_id.get(gid, {})
        details = per_gtfs.get(gid, {})
        ehime_rows.append({**op, "match_class": m.get("match_class", "not_evaluable" if not links_acquired else "E"), "links_operator_name": m.get("links_operator_name", ""), "transport_performance": "unknown" if not links_acquired else details.get("transport_complete"), "business_overview": "unknown" if not links_acquired else details.get("overview_complete"), "driver_count": "unknown" if not links_acquired else details.get("driver_complete"), "2plus_year_gtfs_history": h.get("2plus_year_all_feeds", ""), "3plus_year_gtfs_history": h.get("3plus_year_all_feeds", ""), "ito_rail_check": "伊予鉄" in op.get("agency_name", "") or "いよてつ" in op.get("agency_name", "")})
    if not ehime:
        registry = json.loads((RAW / "gtfs_registry.json").read_text(encoding="utf-8"))["body"] if (RAW / "gtfs_registry.json").exists() else []
        ehime_rows.append({"prefecture": "愛媛県", "agency_name": "伊予鉄バス（確認対象）", "registry_prefecture_code": 38,
            "registry_feed_rows_prefecture_38": sum(str(x.get("feed_pref_id")) == "38" for x in registry),
            "active_gtfs_bus_feeds": 0, "gtfs_status": "not_found_in_official_registry_or_selected_agency_txt",
            "registry_name_token_search": "no 伊予鉄 / いよてつ / Ehime / Matsuyama match in 605-row API response",
            "atlas_crosscheck": "no Ehime / Iyonetsu match in the retrieved 436-feed Transitland Atlas snapshot",
            "match_class": "not_evaluable", "links_operator_name": "", "transport_performance": "unknown",
            "business_overview": "unknown", "driver_count": "unknown", "gtfs_history": "not_applicable_no_feed",
            "limitation": "Absence is limited to these retrieved repositories and this anchor date; it is not a claim that no GTFS exists elsewhere."})
    write_csv(ANALYSIS / "ehime_detail.csv", ehime_rows)

    # Candidate indicator feasibility counts; service quantity is reported as
    # weekday scheduled trips/day and as separate approximate trip-hours/km.
    indicator_defs = [
        ("A", "GTFS service quantity / vehicle count", "weekday GTFS trip-hours/day proxy + LINKS vehicle metric", "vehicle_count"),
        ("B", "GTFS service quantity / driver count", "weekday GTFS trip-hours/day proxy + LINKS driver count", "driver_count"),
        ("C", "passengers / drivers", "LINKS passenger_count + driver_count, same operator/year", "driver_count"),
        ("D", "revenue / drivers", "LINKS revenue + driver_count, same operator/year", "driver_count"),
        ("E", "revenue / GTFS supply", "LINKS revenue + dated GTFS trip-hours/day proxy", "revenue"),
        ("F", "passengers / GTFS supply", "LINKS passenger_count + dated GTFS trip-hours/day proxy", "passenger_count"),
        ("G", "GTFS supply year-over-year", "distinct timetable generations with dated history and version metrics", "gtfs_history"),
        ("H", "driver count year-over-year", "LINKS driver count for two comparable years", "driver_count"),
        ("I", "passenger count year-over-year", "LINKS passenger count for two comparable years", "passenger_count"),
        ("J", "revenue year-over-year", "LINKS revenue for two comparable years", "revenue"),
    ]
    indicator_rows = []
    supply_rows = read_csv(ANALYSIS / "gtfs_supply_yoy.csv") if (ANALYSIS / "gtfs_supply_yoy.csv").exists() else []
    for code, title, requirements, key in indicator_defs:
        if not links_acquired:
            if code == "G" and supply_rows:
                count = sum(truth(x.get("gtfs_supply_yoy_computable")) for x in supply_rows)
                status = "partially_possible_GTFS_only" if count else "not_confirmed_in_downloaded_GTFS_history"
                requested_category = "一部可能（GTFS時刻表だけで供給量前年比を確認）" if count else "今回の取得履歴では未確認"
                note = "Computed only from dated distinct GTFS schedule generations; no LINKS values are implied."
            elif code == "G":
                count = ""
                status = "not_evaluable_GTFS_history_not_run"
                requested_category = "未評価"
                note = "GTFS history metrics have not been generated."
            else:
                count = 0
                status = "not_computable_from_acquired_data_LINKS_source_unavailable"
                requested_category = "不可能（今回取得データだけでは計算不可）"
                note = "0 confirmed computable from retrieved bytes; the true availability in the inaccessible LINKS CSV remains unknown."
        else:
            if code in ("A", "E"):
                count = sum(bool(x["transport_complete"] and per_gtfs[gid]["common_year"]) for gid, x in per_gtfs.items())
            elif code in ("B", "C", "D"):
                count = sum(bool(x["transport_complete"] and x["driver_complete"]) for x in per_gtfs.values())
            elif code == "F":
                count = sum(bool(x["transport_complete"] and per_gtfs[gid]["common_year"]) for gid, x in per_gtfs.items())
            elif code == "G":
                count = sum(truth(x.get("gtfs_supply_yoy_computable")) for x in supply_rows)
                status = "partially_possible_GTFS_only" if count else "not_confirmed_in_downloaded_GTFS_history"
                requested_category = "一部可能（GTFS時刻表だけで供給量前年比を確認）" if count else "今回の取得履歴では未確認"
                note = "Measured from distinct dated timetables in all component feeds; LINKs is not required for this GTFS-only change."
            else:
                count = ""
            if code != "G":
                status = "partially_possible; exact numerator/denominator matching must be checked" if count else "not_computable_from_measured_rows"
                requested_category = "一部可能" if count else "不可能（今回実査した行では計算不可）"
                note = "Computed count is a conservative row-availability count, not a claim that the ratio is comparable across permit classes."
        indicator_rows.append({"indicator": code, "name": title, "feasibility": status, "requested_category": requested_category, "operators_with_required_data": count, "true_population_count_status": "unknown_LINKS_source_unavailable" if not links_acquired and code != "G" else "measured_from_GTFS_history" if code == "G" and status != "not_evaluable_GTFS_history_not_run" else "measured_from_source_rows", "required_data": requirements, "limitations": note})
    write_csv(ANALYSIS / "indicator_feasibility.csv", indicator_rows)

    # Convenience file for the history-fetch step.
    feed_pairs = set()
    for row in read_csv(ANALYSIS / "gtfs_agency_metrics.csv") if (ANALYSIS / "gtfs_agency_metrics.csv").exists() else []:
        feed_pairs.add((row.get("organization_id", ""), row.get("feed_id", "")))
    with (ROOT / "data/processed/gtfs_bus_feed_ids.txt").open("w", encoding="utf-8") as f:
        for org, feed in sorted(feed_pairs):
            f.write(f"{org},{feed}\n")

    gtfs_hist2_total = sum(truth(h.get("2plus_year_all_feeds")) for h in gtfs_hist)
    gtfs_hist3_total = sum(truth(h.get("3plus_year_all_feeds")) for h in gtfs_hist)
    agency_rows = read_csv(ANALYSIS / "gtfs_agency_metrics.csv") if (ANALYSIS / "gtfs_agency_metrics.csv").exists() else []
    feed_rows = read_csv(ANALYSIS / "gtfs_feed_metrics.csv") if (ANALYSIS / "gtfs_feed_metrics.csv").exists() else []
    registry = json.loads((RAW / "gtfs_registry.json").read_text(encoding="utf-8"))["body"] if (RAW / "gtfs_registry.json").exists() else []
    anchor_selection = read_csv(ANALYSIS / "anchor_feed_selection.csv") if (ANALYSIS / "anchor_feed_selection.csv").exists() else []
    selected_feed_count = sum(x.get("status") == "selected" for x in anchor_selection)
    discontinued_count = sum(x.get("status", "").startswith("excluded_discontinued") for x in anchor_selection)
    no_anchor_archive_count = sum(x.get("status") == "no_downloaded_archive_valid_on_anchor" for x in anchor_selection)
    bus_feed_count = sum(x.get("status") == "bus_feed_analyzed" for x in feed_rows)
    no_bus_route_feed_count = sum(x.get("status") == "no_bus_route_type" for x in feed_rows)
    multi_agency_feeds = sum(int(x.get("bus_agency_count") or 0) > 1 for x in feed_rows)
    named_bus_feed_pairs = len({(x.get("organization_id"), x.get("feed_id")) for x in agency_rows})
    not_dated_entities = sum(not truth(x.get("schedule_status_all_dated")) for x in gtfs)
    multi_feed_entities = sum(int(x.get("feed_count") or 0) > 1 for x in gtfs)
    max_feed_count = max((int(x.get("feed_count") or 0) for x in gtfs), default=0)
    municipal_suffix_count = sum(bool(re.search(r"(市|区|町|村)$", x.get("agency_name", ""))) for x in gtfs)
    council_name_count = sum("協議会" in x.get("agency_name", "") for x in gtfs)
    pct = lambda n, d: round(n / d, 4) if d else ""
    data_gap_rows = [
        {"gap_or_grain": "gtfs_registry_records", "count": len(registry), "denominator": len(registry), "rate": 1.0 if registry else "", "unit": "official feed-pair record", "status": "measured", "note": "Registry rows are feed records, not operators."},
        {"gap_or_grain": "gtfs_archive_valid_on_anchor", "count": selected_feed_count, "denominator": len(registry), "rate": pct(selected_feed_count, len(registry)), "unit": "feed archive", "status": "measured_from_zip_feed_info", "note": "Selected archives have an internal feed_info validity window containing 2026-09-29."},
        {"gap_or_grain": "gtfs_marked_discontinued_excluded", "count": discontinued_count, "denominator": len(registry), "rate": pct(discontinued_count, len(registry)), "unit": "feed-pair record", "status": "measured_from_registry", "note": "Discontinued on/before anchor or discontinuation date unknown."},
        {"gap_or_grain": "gtfs_no_downloaded_archive_valid_on_anchor", "count": no_anchor_archive_count, "denominator": len(registry), "rate": pct(no_anchor_archive_count, len(registry)), "unit": "feed-pair record", "status": "measured_from_zip_feed_info", "note": "See anchor_feed_selection.csv for each feed's metadata and validity."},
        {"gap_or_grain": "gtfs_selected_feed_with_bus_route_type", "count": bus_feed_count, "denominator": selected_feed_count, "rate": pct(bus_feed_count, selected_feed_count), "unit": "feed archive", "status": "measured_from_routes.txt", "note": "A feed can contain multiple agency rows; this is not a bus-operator count."},
        {"gap_or_grain": "gtfs_named_bus_agency_feed_pairs", "count": named_bus_feed_pairs, "denominator": bus_feed_count, "rate": pct(named_bus_feed_pairs, bus_feed_count), "unit": "feed archive with agency_name", "status": "measured_from_agency_txt", "note": "One agency/feed pair may yield multiple agency rows."},
        {"gap_or_grain": "gtfs_selected_feed_without_bus_route_type", "count": no_bus_route_feed_count, "denominator": selected_feed_count, "rate": pct(no_bus_route_feed_count, selected_feed_count), "unit": "feed archive", "status": "measured_from_routes.txt", "note": "No route with route_type 3, 11, or 700-799."},
        {"gap_or_grain": "gtfs_feeds_with_multiple_bus_agency_rows", "count": multi_agency_feeds, "denominator": bus_feed_count, "rate": pct(multi_agency_feeds, bus_feed_count), "unit": "feed archive", "status": "measured_from_agency_txt_and_routes_txt", "note": "Multiple distinct agency rows in one feed are preserved, not collapsed."},
        {"gap_or_grain": "gtfs_bus_agency_entities_without_LINKS_comparison", "count": len(gtfs), "denominator": len(gtfs), "rate": 1.0 if gtfs else "", "unit": "agency-derived entity", "status": "not_evaluable_LINKS_source_unavailable", "note": "0 confirmed matches; true match count unknown, not Match E."},
        {"gap_or_grain": "links_dataset_rows_or_operator_count", "count": "", "denominator": "", "rate": "", "unit": "LINKS source rows/operators", "status": "unknown_HTTP_403", "note": "Unknown, not zero; public CKAN API and resource URL returned HTTP 403."},
        {"gap_or_grain": "links_driver_count_completeness", "count": "", "denominator": "", "rate": "", "unit": "LINKS bus operator/year", "status": "unknown_SOURCE_NOT_RETRIEVED", "note": "The 2025 CSV column, year, nonblank count, and grain were not inspectable."},
        {"gap_or_grain": "gtfs_entities_without_dated_schedule_metrics", "count": not_dated_entities, "denominator": len(gtfs), "rate": pct(not_dated_entities, len(gtfs)), "unit": "agency-derived entity", "status": "measured", "note": "Missing/incomplete calendar validity yields blank metrics, not zero."},
        {"gap_or_grain": "gtfs_agency_name_municipal_suffix_signal", "count": municipal_suffix_count, "denominator": len(gtfs), "rate": pct(municipal_suffix_count, len(gtfs)), "unit": "agency-derived entity", "status": "measured_string_signal_not_classification", "note": "agency_name ends in 市/区/町/村; this is not proof of legal operator identity."},
        {"gap_or_grain": "gtfs_agency_name_council_signal", "count": council_name_count, "denominator": len(gtfs), "rate": pct(council_name_count, len(gtfs)), "unit": "agency-derived entity", "status": "measured_string_signal_not_classification", "note": "agency_name contains 協議会; actual operating company remains unverified."},
        {"gap_or_grain": "gtfs_entities_with_multiple_feeds", "count": multi_feed_entities, "denominator": len(gtfs), "rate": pct(multi_feed_entities, len(gtfs)), "unit": "agency-derived entity", "status": "measured", "note": f"Maximum component feeds per entity={max_feed_count}; feed rows are preserved; agency totals are raw feed sums."},
        {"gap_or_grain": "gtfs_history_2plus_years_all_component_feeds", "count": gtfs_hist2_total, "denominator": len(gtfs), "rate": pct(gtfs_hist2_total, len(gtfs)), "unit": "agency-derived entity", "status": "measured_after_history_run", "note": "GTFS-only history; does not imply LINKS or driver completeness."},
        {"gap_or_grain": "gtfs_history_3plus_years_all_component_feeds", "count": gtfs_hist3_total, "denominator": len(gtfs), "rate": pct(gtfs_hist3_total, len(gtfs)), "unit": "agency-derived entity", "status": "measured_after_history_run", "note": "GTFS-only history; does not imply LINKS or driver completeness."},
    ]
    write_csv(ANALYSIS / "data_gap_summary.csv", data_gap_rows)
    grain_rows = [
        {"grain": "registry feed-pairs", "count": len(registry), "unit": "feed record", "note": "Official API rows; not operator count."},
        {"grain": "anchor-valid ZIP feed archives", "count": selected_feed_count, "unit": "feed archive", "note": "Current public ZIP with internal feed_info validity at anchor."},
        {"grain": "selected bus agency.txt rows", "count": len(agency_rows), "unit": "agency record across feed archives", "note": "Preserved at feed/agency grain."},
        {"grain": "selected bus feeds containing agency_name", "count": named_bus_feed_pairs, "unit": "feed archive", "note": "Distinct organization_id/feed_id pairs represented in agency-level output."},
        {"grain": "feeds with multiple bus agency rows", "count": multi_agency_feeds, "unit": "feed archive", "note": "These feeds contribute more than one agency row; examples remain in gtfs_agency_metrics.csv."},
        {"grain": "agency-derived entities", "count": len(gtfs), "unit": "normalized agency/provenance entity", "note": "Not legal-operator verified."},
        {"grain": "distinct raw agency_name strings", "count": len({x.get("agency_name", "") for x in gtfs}), "unit": "display name", "note": "A name may appear in multiple publisher-qualified entities."},
        {"grain": "entities with multiple component feeds", "count": multi_feed_entities, "unit": "agency-derived entity", "note": f"Maximum feed count={max_feed_count}; component feed IDs and per-feed rows remain in metrics."},
        {"grain": "municipal-suffix names", "count": municipal_suffix_count, "unit": "agency-derived entity", "note": "Name signal only; not an entity type determination."},
        {"grain": "council-name signal", "count": council_name_count, "unit": "agency-derived entity", "note": "Name signal only; actual operating company unresolved."},
        {"grain": "LINKS source grain", "count": "", "unit": "unknown", "note": "Cannot distinguish operator/region/branch/permit repetition without CSV and specification."},
    ]
    write_csv(ANALYSIS / "grain_summary.csv", grain_rows)
    write_report(gtfs, matches, links_acquired, transport_n, overview_n, driver_n, hist2_n, hist3_n, full_n, gtfs_hist2_total, gtfs_hist3_total, prefecture_rows, ehime_rows, indicator_rows, "available and parsed" if links_acquired else "UNAVAILABLE: official CKAN API and resource downloads returned HTTP 403", f"official API registry=605 records; anchor-valid archive={len(feed_rows)}; bus agency.txt rows={len(agency_rows)}; agency-derived entities={len(gtfs)}")
    print(json.dumps({"gtfs_operator_entities": len(gtfs), "links_acquired": links_acquired, "matched": matched_n, "transport_complete": transport_n, "business_overview_complete": overview_n, "driver_complete": driver_n, "history_2plus": hist2_n, "history_3plus": hist3_n, "full_eligible": full_n, "prefecture_rows": len(prefecture_rows), "ehime_rows": len(ehime_rows)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
