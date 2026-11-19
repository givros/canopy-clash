"""Summarize actual native bot matches and map their movement against the authored routes."""
from argparse import ArgumentParser
from collections import Counter
import json
import math
from hashlib import file_digest
from pathlib import Path
from statistics import mean, median

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
from matplotlib.lines import Line2D
from matplotlib.patches import Circle


SOURCE = Path(__file__).resolve().parent
PROJECT = SOURCE.parents[2]
REVIEW = SOURCE / "Review"


def region(x, y, z):
    if x > 23 and z > 7.5:
        return "Temple terraces"
    if y > 34:
        return "Eastern gallery"
    if y < -10:
        return "Western cloister"
    return "Gate, bridge and plaza"


def temple_height(x, y, z):
    if x > 45 and z > 14:
        return "Sanctuary"
    if x > 23 and z > 7.5:
        return "Upper approach"
    return "Rest of arena"


def inspect(label, nav):
    logfile = PROJECT / "Saved/Deathmatch" / label / "Review.log"
    rows = [l.split("CB|", 1)[1].split("|") for l in logfile.read_text(encoding="utf-8").splitlines()
            if "LogCanopyBalance:" in l and "CB|" in l]
    results = [{"round": int(r[1]), "red": int(r[2]), "blue": int(r[3]), "seconds": float(r[4]),
                "participants": int(r[5])} for r in rows if r[0] == "result"]
    if not results:
        raise ValueError("No completed matches at " + str(logfile))
    finished = {game["round"] for game in results}
    seeds = [int(row[1]) for row in rows if row[0] == "seed"]
    rows = [row for row in rows if row[0] != "seed" and int(row[1]) in finished]
    centers = []
    for team in ("Red", "Blue"):
        points = [s["point_m"] for n, s in nav["spawns"].items() if n.startswith(team)]
        centers.append([mean(p[i] for p in points) for i in range(3)])
    contacts = [(int(r[3]), *map(float, r[5:8])) for r in rows if r[0] == "contact"]
    positions = [(int(r[4]), *map(float, r[5:8])) for r in rows if r[0] == "position"]
    encounters = [(int(r[2]), *map(float, r[3:9])) for r in rows if r[0] == "encounter"]
    agents = [r for r in rows if r[0] == "agent"]
    pts_total = sum(r["red"] + r["blue"] for r in results)
    at_spawn = 0
    for killer_team, x, y, z in contacts:
        bx, by, bz = centers[1-killer_team]
        at_spawn += math.hypot(x-bx,y-by) < 6.5 and abs(z-bz) < 4.3
    distance = [math.dist(r[1:4],r[4:7]) for r in encounters]
    runtime = logfile.parent / "Runtime"
    def sha256(relative):
        with (runtime / relative).open("rb") as asset:
            return file_digest(asset, "sha256").hexdigest()
    report = dict(seed=seeds[0] if seeds else None, matches=results,red_wins=sum(r["red"]>r["blue"] for r in results),
                  blue_wins=sum(r["blue"]>r["red"] for r in results),
                  total_score_events=pts_total,located_score_events=len(contacts),
                  eliminations_inside_victim_home_base=at_spawn,
                  victim_locations_by_region=dict(Counter(region(*p[1:]) for p in contacts)),
                  movement_samples_by_region=dict(Counter(region(*p[1:]) for p in positions)),
                  bot_rounds=len(agents),walked_m=round(sum(float(r[6]) for r in agents)),
                  minimum_distance_per_bot_per_round_m=min(float(r[6]) for r in agents),
                  movement_requests_stalled_five_seconds=sum(int(r[7]) for r in agents),
                  longest_stall_s=max(float(r[8]) for r in agents),
                  all_ten_bots_present=all(r["participants"]==10 for r in results),
                  raw_log=str(logfile.relative_to(PROJECT)).replace("\\","/"),
                  map_sha256=sha256("Content/AstraTemple/Maps/L_CanopyDeathmatch.umap"),
                  editor_module_sha256=sha256("Binaries/Win64/UnrealEditor-gameAstraForest.dll"))
    if distance:
        report["engagement_distance_m"] = dict(minimum=min(distance),median=round(median(distance),1),
             p90=round(sorted(distance)[int((len(distance)-1)*.90)],1),maximum=round(max(distance),1))
        report["engagements_from_or_onto_terraces"] = sum("Temple terraces" in (region(*p[1:4]),region(*p[4:7])) for p in encounters)
        report["temple_activity"] = {
            name:{
                "movement_samples":dict(Counter(temple_height(x,y,z) for team,x,y,z in positions if team==side)),
                "scoring_positions":dict(Counter(temple_height(*p[1:4]) for p in encounters if p[0]==side)),
                "opponents_eliminated_more_than_3m_below":sum(p[3]-p[6]>3 for p in encounters if p[0]==side)}
            for side,name in enumerate(("Red","Blue"))}
    return report, positions, contacts, centers


def chart(nav, positions, contacts, centers, rounds):
    if not positions:
        return
    fig,ax = plt.subplots(figsize=(11.2,6.5),layout="constrained")
    fig.patch.set_facecolor("#f5f3ec")
    ax.set_facecolor("#e8ece2")
    for label,legs in nav["legs"].items():
        lines = [[p[:2] for p in leg["points_m"]] for leg in legs]
        ax.add_collection(LineCollection(lines,colors="#667365",linewidths=1.8,alpha=.9,zorder=1))
    ax.scatter([p[1] for p in positions],[p[2] for p in positions],s=6,c="#456344",alpha=.19,edgecolors="none",zorder=2)
    palette=["#b23539","#2768aa"]
    for team,color in enumerate(palette):
        pts=[p for p in contacts if p[0]==team]
        ax.scatter([p[1] for p in pts],[p[2] for p in pts],s=10,facecolors="none",edgecolors=color,linewidths=.62,alpha=.57,zorder=3)
        x,y,_=centers[team]
        ax.add_patch(Circle((x,y),6.5,color=color,alpha=.18))
        ax.plot(x,y,marker="D",color=color,ms=6)
    for s,at in [("Roots Gate",(-96,3)),("East Quay",(16,25)),("Eastern gallery",(-39,58)),("Western cloister",(-51,-65)),("Temple terraces",(34,5))]:
        ax.text(*at,s,color="#273c32",size=10,weight="bold")
    ax.set_aspect("equal");ax.set_xlim(-103,80);ax.set_ylim(-72,68)
    ax.set_xlabel("World X (metres)");ax.set_ylabel("World Y (metres)")
    fig.suptitle("Canopy Clash   |   Bot movement and eliminations",x=.5,fontsize=18,weight="bold",color="#20372d")
    ax.set_title(f"{rounds} full matches  ·  positions sampled every four seconds  ·  6.5 m enemy exclusion zones",fontsize=10,color="#475c50",pad=9)
    ax.legend(handles=[Line2D([],[],marker="o",ls="",mfc="none",mec=palette[0],label="Red point"),
                       Line2D([],[],marker="o",ls="",mfc="none",mec=palette[1],label="Blue point"),
                       Line2D([],[],marker=".",ls="",color="#456344",label="Bot position"),
                       Line2D([],[],color="#667365",label="NavMesh route")],loc="lower right",ncols=2,fontsize=8,framealpha=.95)
    fig.savefig(REVIEW/"ArenaActivity.png",dpi=170)
    plt.close(fig)


def main():
    parser=ArgumentParser(description=__doc__)
    parser.add_argument("runs",nargs="+")
    parser.add_argument("--final",nargs="+",help="Combine these runs from the delivered map in the chart and totals")
    args=parser.parse_args()
    nav=json.loads((SOURCE/"ArenaNavigation.json").read_text())
    output={"method":"Native Unreal dedicated process, loopback only. Ten actual bot controllers. Fixed 30 Hz simulation. Active combat ends at the normal score limit. Movement distances exclude teleports. Movement stalls require a live path-following request.","runs":{}}
    final=args.final or [args.runs[-1]]
    final_positions,final_contacts,final_matches=[],[],[]
    for name in dict.fromkeys(args.runs+final):
        data,positions,contacts,centers=inspect(name,nav)
        output["runs"][name]=data
        if name in final:
            final_positions.extend(positions)
            final_contacts.extend(contacts)
            final_matches.extend(data["matches"])
    red=sum(game["red"] for game in final_matches)
    blue=sum(game["blue"] for game in final_matches)
    cohorts=[output["runs"][run] for run in final]
    if any(len({r[field] for r in cohorts}) != 1 for field in ("map_sha256","editor_module_sha256")):
        raise ValueError("Final match groups must use the same map and module.")
    spreads=[abs(game["red"]-game["blue"]) for game in final_matches]
    output["delivered"]={
        "runs":final,"matches":len(final_matches),"score":[red,blue],
        "cohort_seeds":[output["runs"][run]["seed"] for run in final],
        "red_point_share":round(red/(red+blue),4),
        "wins":[sum(g["red"]>g["blue"] for g in final_matches),sum(g["blue"]>g["red"] for g in final_matches)],
        "draws":sum(g["red"]==g["blue"] for g in final_matches),
        "median_winning_margin":median(spreads),"rounds_decided_by_three_points_or_less":sum(s<=3 for s in spreads),
        "total_time_in_active_play_minutes":round(sum(g["seconds"] for g in final_matches)/60,1),
        "movement_requests_stalled_five_seconds":sum(output["runs"][r]["movement_requests_stalled_five_seconds"] for r in final),
        "eliminations_inside_victim_home_base":sum(output["runs"][r]["eliminations_inside_victim_home_base"] for r in final),
        "map_sha256":cohorts[0]["map_sha256"],"editor_module_sha256":cohorts[0]["editor_module_sha256"],
        "samples_by_team_and_region":{
            name:dict(Counter(region(x,y,z) for t,x,y,z in final_positions if t==team))
            for team,name in enumerate(("Red","Blue"))},
        "deaths_within_20m_of_own_start_center":{
            name:sum(killer!=team and math.dist((x,y),centers[team][:2])<20 for killer,x,y,z in final_contacts)
            for team,name in enumerate(("Red","Blue"))}}
    chart(nav,final_positions,final_contacts,centers,len(final_matches))
    (REVIEW/"BalanceReport.json").write_text(json.dumps(output,indent=2),encoding="utf-8")


if __name__=="__main__":
    main()
