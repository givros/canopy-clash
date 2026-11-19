"""Compare full native five-on-five matches using the actual home locations in each layout."""
from collections import Counter
from pathlib import Path
from statistics import mean, median
import json
import math

ROOT=Path(__file__).resolve().parents[3]
REVIEW=Path(__file__).resolve().parent/"Review"
OLD_BLUE=(14.0,25.68333)
INNER_BLUE=((11.1+13.7+15.4+11.45+13.75+15.5)/6,(2.3+2.3+3.6+4.05+5.35+5)/6)
MIDDLE_BLUE=((11.25+13.65+16.2+11.4+13.9+16.3)/6,(14.8+14.7+14.8+17.35+17+17)/6)
LOWER_BLUE=((11.2+13.5+15.8+11.0+13.8+16.)/6,(6.7+6.7+6.7+12.15+12.05+12.15)/6)
TWO_EXITS=((11.1+13.7+15.4+11.0+13.8+16.)/6,(2.3+2.3+3.6+12.15+12.05+12.15)/6)
INNER_SHELTER=((11.1+13.7+15.4+11.2+13.5+15.8)/6,(2.3+2.3+3.6+6.7+6.7+6.7)/6)
COLONNADE=((11.1+13.7+15.4+11.45+11.25+15.5)/6,(2.3+2.3+3.6+4.05+14+14)/6)
PROTECTED=((11.8+13.1+15.7+10.5+13.1+15.7)/6,2.5)
ALCOVE=(10.041666666666666,-.25)
RED=(-84.35,12.41667)

def area(p):
    x,y,z=p
    if x>23 and z>7.5:return "Upper terraces"
    if y<-10:return "West cloister"
    if y>34:return "East gallery"
    if x<-49:return "Gate and Red bank"
    if x<-8:return "Causeway"
    return "Blue quay and plaza"


def inspect(runs,blue,red=RED):
    scores=[];zones=Counter();original=Counter();regions=Counter();stalls=[];players=[];times=[];ranges=[]
    respawns={}
    cohorts=[]
    yield_actions=0
    scoring_regions=Counter()
    casualty_regions=Counter()
    safety_returns=[]
    seeds=[]
    for run in runs:
        path=ROOT/"Saved/Deathmatch"/run/"Review.log"
        if not path.exists():continue
        lines=path.read_text(errors="replace").splitlines()
        yield_actions+=sum("TCrowdYield|" in l for l in lines)
        rows=[l.split("CB|",1)[1].split("|") for l in lines if "CB|" in l]
        finished={int(r[1]) for r in rows if r[0]=="result"}
        seeds.extend(int(r[1]) for r in rows if r[0]=="seed")
        match_results=[(int(r[2]),int(r[3])) for r in rows if r[0]=="result"]
        if match_results:
            red_total=sum(v[0] for v in match_results)
            blue_total=sum(v[1] for v in match_results)
            cohorts.append(dict(run=run,seed=next((int(r[1]) for r in rows if r[0]=="seed"),None),
                matches=len(match_results),points=[red_total,blue_total],
                wins=[sum(a>b for a,b in match_results),sum(b>a for a,b in match_results)],
                red_point_share=round(red_total/(red_total+blue_total),4)))
        for r in rows:
            if int(r[1]) not in finished:continue
            if r[0]=="result":
                scores.append([int(r[2]),int(r[3])]);times.append(float(r[4]))
            if r[0]=="agent":players.append([r[2],int(r[3]),float(r[6]),int(r[7]),float(r[8])])
            if r[0]=="position":
                x,y,z=map(float,r[5:8])
                lane="Terrace" if x>23 and z>7.5 else "Cloister" if y<-10 else "Gallery" if y>34 else "Gate and causeway"
                regions[(int(r[4]),lane)]+=1
            if r[0]=="slow":stalls.append({"run":run,"round":int(r[1]),"time":float(r[2]),"name":r[3],"position_m":[*map(float,r[4:7])],"next_path_point_m":[*map(float,r[7:10])]})
            if r[0]=="encounter":
                t=int(r[2]);p=list(map(float,r[3:6]));q=list(map(float,r[6:9]));ranges.append(math.dist(p,q))
                scoring_regions[(t,area(p))]+=1
                casualty_regions[(1-t,area(q))]+=1
            if r[0]=="safetyreturn":
                z=float(r[6])
                safety_returns.append(dict(run=run,round=int(r[1]),team=("Red","Blue")[int(r[2])],player=r[3],
                    point_m=[float(n) for n in r[4:7]],cause="below_level" if z<-6.5 else "enemy_base"))
            if r[0]=="respawn":
                team="Red" if int(r[2])==0 else "Blue"
                spot=respawns.setdefault(team,{}).setdefault(r[4]+", "+r[5],[])
                spot.append([float(r[6]),float(r[7]),int(r[8])])
            if r[0]=="contact":
                t=int(r[3]);q=list(map(float,r[5:7]));home=blue if t==0 else red
                if math.dist(home,q)<20:zones["Blue" if t==0 else "Red"]+=1
                if math.dist(OLD_BLUE if t==0 else RED,q)<20:original["Blue" if t==0 else "Red"]+=1
    red=sum(s[0] for s in scores);b=sum(s[1] for s in scores)
    return dict(rounds=len(scores),seeds=seeds,cohorts=cohorts,logged_yield_actions=yield_actions,red_wins=sum(s[0]>s[1] for s in scores),blue_wins=sum(s[1]>s[0] for s in scores),
        points=[red,b],red_point_share=round(red/max(1,red+b),4),median_score_gap=median([abs(x-y) for x,y in scores]) if scores else None,
        mean_round_seconds=round(mean(times),1) if times else None,deaths_within_20m_of_own_start_center=dict(zones),deaths_within_20m_of_original_start_center=dict(original),
        median_engagement_range_m=round(median(ranges),1) if ranges else None,completed_bot_rounds=len(players),
        minimum_distance_per_bot_round_m=min([p[2] for p in players],default=None),
        total_bot_distance_m=round(sum(p[2] for p in players)),moving_requests_stalled_5s=len(stalls),
        max_stall_s=max([p[4] for p in players],default=0),regions_by_team={["Red","Blue"][i]:{k:v for (t,k),v in regions.items() if t==i} for i in [0,1]},
        scoring_locations_by_team={team:{k:n for (t,k),n in scoring_regions.items() if t==i} for i,team in enumerate(("Red","Blue"))},
        death_locations_by_team={team:{k:n for (t,k),n in casualty_regions.items() if t==i} for i,team in enumerate(("Red","Blue"))},
        safety_return_counts=dict(Counter(event["cause"] for event in safety_returns)),safety_returns=safety_returns,
        respawn_selections={team:{point:dict(count=len(events),mean_nearest_ally_m=round(mean(e[0] for e in events if e[0]>=0),2) if any(e[0]>=0 for e in events) else None,
            mean_nearest_enemy_m=round(mean(e[1] for e in events if e[1]>=0),2) if any(e[1]>=0 for e in events) else None,
            entries_with_enemy_sightline=sum(e[2]>0 for e in events)) for point,events in samples.items()} for team,samples in respawns.items()},
        stalls=stalls,results=scores)

if __name__=="__main__":
    sets={"original_24":(["BalanceFinal"],OLD_BLUE),"unmodified_ford_6":(["QuayImpactBefore"],OLD_BLUE)}
    for label,folder,blue in [("two_walls","QuayA",OLD_BLUE),("three_walls","QuayB",OLD_BLUE),("three_walls_with_crowd","CrowdB",OLD_BLUE),("shared_rally","CrowdLaneB",OLD_BLUE),("widened_openings","CrowdLaneC",OLD_BLUE),("inner_plaza","CrowdLaneD",INNER_BLUE),("middle_quay","CrowdLaneE",MIDDLE_BLUE),("forward_entry","CrowdForwardE",MIDDLE_BLUE),("sheltered_quay","CrowdForwardF",LOWER_BLUE),("forward_inner","CrowdForwardD",INNER_BLUE),("two_exits","CrowdTwoExits",TWO_EXITS),("dual_shelter","CrowdDualShelter",TWO_EXITS),("inner_shelter","CrowdInnerShelter",INNER_SHELTER),("colonnade","CrowdPortico",COLONNADE),("protected_quay","QuayShelterStudy",PROTECTED),("original_lanes_final_rules","QuayAcceptance",PROTECTED),("inner_control_final_rules","QuayInnerFinalControl",INNER_BLUE),("adaptive_lanes","AdaptiveQuay",PROTECTED),("approach","ApproachQuay",PROTECTED),("approach_yield","QuayYield",PROTECTED),("stable_cadence_yield","QuayYieldStable",PROTECTED)]:
        sets[label]=([folder+"Rounds1",folder+"Rounds2"],blue)
    sets["midspan_approach"]=(["MidspanApproach1","MidspanApproach2"],PROTECTED)
    sets["native_terraces"]=(["NativeTerraces1","NativeTerraces2"],PROTECTED)
    sets["western_approach"]=(["TerraceCloister1","TerraceCloister2"],PROTECTED)
    sets["filtered_western_approach"]=(["DeliveredMatchSet1","DeliveredMatchSet2"],PROTECTED)
    sets["quay_alcove"]=(["BlueAlcoveMatches1","BlueAlcoveMatches2"],ALCOVE)
    sets["quay_alcove_causeway_terraces"]=(["BlueAlcoveTerrace1","BlueAlcoveTerrace2"],ALCOVE)
    sets["quay_alcove_first_landing"]=(["BlueAlcoveLanding1","BlueAlcoveLanding2"],ALCOVE)
    for label, prefix in [("west_spring_previous", "CanopyFinal"), ("west_spring_release", "ReleaseCloister")]:
        sets[label] = ([prefix + seed for seed in ("April", "Birch", "Cedar", "Dawn")], ALCOVE)
    results={k:inspect(*v) for k,v in sets.items()}
    (REVIEW/"QuayBalance.json").write_text(json.dumps({"method":"Every row uses completed native ten-bot matches, default 50 points and 600 seconds. Distance to the team's spawn centre is horizontal. Traces are collected independently of the match outcome.","results":results},indent=2))
    for k,r in results.items(): print(k,r["rounds"],r["red_wins"],r["blue_wins"],r["red_point_share"],r["deaths_within_20m_of_own_start_center"],r["moving_requests_stalled_5s"])
