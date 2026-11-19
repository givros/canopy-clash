#include "TempleHUD.h"
#include "TempleFighter.h"
#include "TempleMatch.h"
#include "TempleGameInstance.h"

#include "Blueprint/WidgetTree.h"
#include "Brushes/SlateColorBrush.h"
#include "Components/Button.h"
#include "Components/CanvasPanel.h"
#include "Components/CanvasPanelSlot.h"
#include "Components/EditableTextBox.h"
#include "Components/TextBlock.h"
#include "Engine/World.h"
#include "Fonts/FontMeasure.h"
#include "Framework/Application/SlateApplication.h"
#include "InputCoreTypes.h"
#include "Rendering/DrawElements.h"
#include "Rendering/SlateRenderer.h"
#include "Styling/CoreStyle.h"
#include "Widgets/SLeafWidget.h"
#include "Widgets/SOverlay.h"

namespace TempleUI
{
const FLinearColor White = FLinearColor::FromSRGBColor(FColor(244,246,240));
const FLinearColor Muted = FLinearColor::FromSRGBColor(FColor(182,197,193));
const FLinearColor Gold = FLinearColor::FromSRGBColor(FColor(236,196,112));
const FLinearColor Red = FLinearColor::FromSRGBColor(FColor(251,114,104));
const FLinearColor Blue = FLinearColor::FromSRGBColor(FColor(102,200,251));
const FLinearColor Dark(.011f,.019f,.021f,.92f);
const FLinearColor Rule(.14f,.18f,.18f,.88f);
constexpr int32 RowsPerPage = 7;

FLinearColor Side(uint8 Team) { return Team == 0 ? Red : Team == 1 ? Blue : Muted; }
FString TeamName(uint8 Team) { return Team == 0 ? TEXT("RED") : Team == 1 ? TEXT("BLUE") : TEXT("UNASSIGNED"); }
FString Clock(int32 Seconds) { Seconds = FMath::Max(0, Seconds); return FString::Printf(TEXT("%d:%02d"), Seconds / 60, Seconds % 60); }
FLinearColor Alpha(FLinearColor Color, float Opacity) { Color.A = Opacity; return Color; }

class FPaint
{
public:
    FPaint(const FGeometry& Geo, FSlateWindowElementList& List, int32 Layer, float Factor)
        : Geometry(Geo), DrawList(List), Base(Layer), Scale(Factor), Width(Geo.GetLocalSize().X/Factor), Height(Geo.GetLocalSize().Y/Factor) {}

    void Box(float X, float Y, float W, float H, FLinearColor Color, int32 Z=0) const
    {
        if (W <= 0 || H <= 0) return;
        const FPaintGeometry Area = Geometry.ToPaintGeometry(FVector2f(W,H), FSlateLayoutTransform(Scale,FVector2f(X*Scale,Y*Scale)));
        FSlateDrawElement::MakeBox(DrawList,Base+Z,Area,FCoreStyle::Get().GetBrush("WhiteBrush"),ESlateDrawEffect::None,Color);
    }
    void Line(std::initializer_list<FVector2f> Vertices, FLinearColor Color, float Thickness=1.5f, int32 Z=2) const
    {
        TArray<FVector2f> Points;
        Points.Reserve(static_cast<int32>(Vertices.size()));
        for (const FVector2f& P:Vertices) Points.Add(P);
        const FPaintGeometry Area=Geometry.ToPaintGeometry(FVector2f(Width,Height),FSlateLayoutTransform(Scale));
        FSlateDrawElement::MakeLines(DrawList,Base+Z,Area,MoveTemp(Points),ESlateDrawEffect::None,Color,true,Thickness);
    }
    FSlateFontInfo Font(float Points, bool bBold) const
    { return FCoreStyle::GetDefaultFontStyle(bBold ? FName("Bold") : FName("Regular"),Points); }
    FVector2D Measure(const FString& Value,const FSlateFontInfo& Face) const
    { return FSlateApplication::Get().GetRenderer()->GetFontMeasureService()->Measure(Value,Face); }
    void Text(float X,float Y,const FString& Value,float Pt,FLinearColor Color,bool bBold=true,float Anchor=0.f,int32 Z=3,float MaxWidth=0.f) const
    {
        if (Value.IsEmpty()) return;
        const FSlateFontInfo Face=Font(Pt,bBold);
        FString Printed=Value;
        FVector2D Size=Measure(Printed,Face);
        if (MaxWidth>0 && Size.X>MaxWidth)
        {
            const FString Ellipsis=TEXT("…");
            int32 Low=0,High=Printed.Len();
            while(Low<High)
            {
                const int32 Mid=(Low+High+1)/2;
                if(Measure(Printed.Left(Mid)+Ellipsis,Face).X<=MaxWidth) Low=Mid; else High=Mid-1;
            }
            Printed=Printed.Left(Low)+Ellipsis; Size=Measure(Printed,Face);
        }
        const FPaintGeometry Area=Geometry.ToPaintGeometry(FVector2f(Size.X+2,Size.Y+2),FSlateLayoutTransform(Scale,FVector2f((X-Size.X*Anchor)*Scale,Y*Scale)));
        FSlateDrawElement::MakeText(DrawList,Base+Z,Area,Printed,Face,ESlateDrawEffect::None,Color);
    }
    void Emblem(float X,float Y,float S,uint8 Team) const
    {
        const FLinearColor C=Side(Team);
        if(Team==0)
        {
            Line({{X-S,Y+S*.72f},{X,Y-S},{X+S,Y+S*.72f}},C,2.1f);
            Line({{X-S*.48f,Y+S*.7f},{X,Y-S*.14f},{X+S*.48f,Y+S*.7f}},C,1.5f);
        }
        else
        {
            Line({{X,Y-S},{X+S*.92f,Y},{X,Y+S},{X-S*.92f,Y},{X,Y-S}},C,1.9f);
            Line({{X-S*.40f,Y},{X+S*.40f,Y}},C,1.5f);
        }
    }
    void Carbine(float X,float Y,float S,FLinearColor C) const
    {
        Line({{X,Y+S*.15f},{X+S*.20f,Y+S*.15f},{X+S*.32f,Y},{X+S*.78f,Y},{X+S*.81f,Y+S*.085f},{X+S,Y+S*.085f}},C,1.8f);
        Line({{X,Y+S*.15f},{X,Y+S*.28f},{X+S*.30f,Y+S*.16f},{X+S*.38f,Y+S*.16f},{X+S*.35f,Y+S*.31f}},C,1.8f);
        Line({{X+S*.48f,Y+S*.13f},{X+S*.55f,Y+S*.31f},{X+S*.61f,Y+S*.27f},{X+S*.57f,Y+S*.14f},{X+S*.80f,Y+S*.14f}},C,1.8f);
    }
    const FGeometry& Geometry;
    FSlateWindowElementList& DrawList;
    int32 Base;
    float Scale,Width,Height;
};

struct FBoard
{
    float X, Y, W, H;
    FBoard(float ScreenW,float ScreenH,bool bEnd)
    {
        W=FMath::Min(908.f,ScreenW-64.f); H=bEnd?478.f:450.f;
        X=(ScreenW-W)*.5f;Y=(ScreenH-H)*.5f;
    }
};

struct FMenu
{
    float X,Y,W,H;
    FMenu(float ScreenW,float ScreenH,bool Controls)
    {
        W=Controls?414.f:324.f; H=Controls?433.f:392.f;
        X=FMath::Min(48.f,ScreenW*.05f); Y=(ScreenH-H)*.5f;
    }
};

class STempleInstruments final : public SLeafWidget
{
public:
    SLATE_BEGIN_ARGS(STempleInstruments) {} SLATE_ARGUMENT(TWeakObjectPtr<UTempleCombatHUD>, OwnerHUD) SLATE_END_ARGS()
    void Construct(const FArguments& Args) { Owner=Args._OwnerHUD; SetVisibility(EVisibility::HitTestInvisible); ForceVolatile(true); }
    virtual FVector2D ComputeDesiredSize(float) const override { return FVector2D::ZeroVector; }
    virtual int32 OnPaint(const FPaintArgs&,const FGeometry& G,const FSlateRect&,FSlateWindowElementList& L,int32 Layer,const FWidgetStyle&,bool) const override
    { return Owner.IsValid() ? Owner->DrawInstruments(G,L,Layer) : Layer; }
private:
    TWeakObjectPtr<UTempleCombatHUD> Owner;
};

void ScoreStrip(const FPaint& P,const ATempleGameState& Match,int32 Remaining)
{
    const float X=P.Width*.5f,Y=14;
    P.Box(X-144,Y,288,45,Dark);
    for(uint8 Team=0;Team<2;++Team)
    {
        const bool R=Team==0;const float Edge=R?X-144:X+142;const float Center=R?X-94:X+94;
        P.Box(Edge,Y,2,45,Side(Team),1);
        P.Box(R?X-141:X+48,Y+42,93,3,Alpha(Side(Team),.34f),1);
        P.Emblem(Center+(R?-28:28),Y+16,6,Team);
        P.Text(Center+(R?-28:28),Y+24,TeamName(Team),8,Side(Team),true,.5f);
        P.Text(Center+(R?10:-10),Y+3,FString::FromInt(R?Match.RedScore:Match.BlueScore),23,White,true,.5f);
    }
    P.Box(X-44,Y+8,1,28,Rule,1);P.Box(X+43,Y+8,1,28,Rule,1);
    P.Text(X,Y+2,Clock(Remaining),17,Remaining<=30&&Match.Phase==2?Gold:White,true,.5f);
    P.Text(X,Y+26,FString::Printf(TEXT("FIRST TO %d"),Match.ScoreLimit),8,Muted,true,.5f);
}

void Feed(const FPaint& P,const ATempleGameState& Match,double Now)
{
    const float Right=P.Width-21;
    int32 Visible=0;
    for(int32 I=Match.Feed.Num()-1;I>=0&&Visible<4;--I)
    {
        const FTempleFeedEntry& E=Match.Feed[I];
        const float Age=Now-E.ServerTime;
        if(Age>6.0f||Age<-.25f)continue;
        const float A=FMath::Clamp((6.f-Age)/.7f,0.f,1.f);
        const float Y=77.f+Visible*24.f;const float NameCap=109.f;
        const float K=FMath::Min(NameCap,static_cast<float>(P.Measure(E.Killer,P.Font(10,true)).X));
        const float V=FMath::Min(NameCap,static_cast<float>(P.Measure(E.Victim,P.Font(10,true)).X));
        const float W=K+V+47.f; const float L=Right-W;
        P.Box(L,Y,W,21,Alpha(Dark,A*.83f));
        P.Box(L,Y,2,21,Alpha(Side(E.KillerTeam),A),1);
        P.Text(L+8,Y+2,E.Killer,10,Alpha(Side(E.KillerTeam),A),true,0,3,NameCap);
        P.Carbine(L+K+13,Y+7,18,Alpha(White,A*.85f));
        P.Text(Right-7,Y+2,E.Victim,10,Alpha(Side(E.VictimTeam),A),true,1,3,NameCap);
        ++Visible;
    }
}

void Vitals(const FPaint& P,const ATempleFighter& Fighter,uint8 Team)
{
    const float X=24,Y=P.Height-80;const float HP=Fighter.GetHealth();
    const float Fraction=FMath::Clamp(HP/FMath::Max(1.f,static_cast<float>(Fighter.GetMaxHealth())),0.f,1.f);
    const FLinearColor Health=Fraction<=.25f?Red:White;
    P.Box(X,Y,194,55,Dark);P.Box(X,Y,3,55,Side(Team),1);
    P.Emblem(X+21,Y+17,7,Team);P.Text(X+36,Y+7,TeamName(Team)+TEXT(" TEAM"),10,Side(Team));
    P.Box(X+12,Y+34,12,3,Health,2);P.Box(X+16.5f,Y+29.5f,3,12,Health,2);
    P.Text(X+34,Y+23,TEXT("HEALTH"),10,Muted);
    P.Text(X+182,Y-1,FString::FromInt(FMath::CeilToInt(HP)),26,Health,true,1);
    for(int32 I=0;I<10;++I)
    {
        const float L=X+11+I*17.4f;P.Box(L,Y+46,15.3f,3,Rule,1);
        P.Box(L,Y+46,15.3f*FMath::Clamp(Fraction*10-I,0.f,1.f),3,Health,2);
    }
    if(Fighter.IsSpawnProtected())
    {
        P.Box(X,Y-23,140,20,Dark);P.Text(X+8,Y-22,TEXT("SPAWN PROTECTION"),10,Gold);
    }
    const float A=P.Width-204,B=P.Height-80;P.Box(A,B,180,55,Dark);
    P.Carbine(A+10,B+10,33,Muted);P.Text(A+51,B+5,TEXT("CANOPY CARBINE"),10,Muted);
    const bool Reload=Fighter.IsReloading(); const int32 Loaded=Fighter.GetMagazineAmmo();
    P.Text(A+91,B+18,FString::FromInt(Loaded),23,Loaded<=5?Gold:White,true,1);
    P.Text(A+101,B+27,FString::Printf(TEXT("/  %d"),Fighter.GetReserveAmmo()),13,Muted);
    P.Box(A+10,B+48,160,2,Rule,1);
    const float Progress=Reload?Fighter.GetReloadAlpha():static_cast<float>(Loaded)/FMath::Max(1,Fighter.GetMagazineCapacity());
    P.Box(A+10,B+48,160*FMath::Clamp(Progress,0.f,1.f),2,Reload?Gold:Side(Team),2);
    if(Reload||Loaded==0)
    {
        const FString Prompt=Reload?TEXT("RELOADING"):Fighter.GetReserveAmmo()>0?TEXT("R   RELOAD"):TEXT("OUT OF AMMO");
        P.Box(A+68,B-23,112,20,Dark);P.Text(A+174,B-22,Prompt,10,Gold,true,1);
    }
}

void Aim(const FPaint& P,const ATempleFighter& F,const APlayerController& Controller,float Now,float Spread)
{
    const float CX=P.Width*.5f,CY=P.Height*.5f;
    if(!F.IsReloading())
    {
        if(!F.IsAiming())
        {
            const float Gap=FMath::Clamp(Spread,3.5f,15.f);
            for(FVector2f D:{FVector2f(1,0),FVector2f(-1,0),FVector2f(0,1),FVector2f(0,-1)})
            {
                const FVector2f Center(CX,CY),A=Center+D*Gap,B=A+D*5.f;
                P.Line({A,B},FLinearColor(0,0,0,.89f),3.9f,1);P.Line({A,B},White,1.9f,2);
            }
        }
        P.Box(CX-1.9f,CY-1.9f,3.8f,3.8f,FLinearColor(0,0,0,.90f),1);P.Box(CX-1.f,CY-1.f,2.f,2.f,White,2);
    }
    const float HitAge=Now-F.GetLocalHitTime();
    if(HitAge>=0 && HitAge<.25f)
    {
        const bool Kill=F.GetLocalHitWasKill();const float Op=1.f-HitAge/.25f;
        const float A=6.f+HitAge*11.f,B=A+(Kill?6.f:4.f);
        for(int32 I:{-1,1})for(int32 J:{-1,1})
        {
            P.Line({{CX+A*I,CY+A*J},{CX+B*I,CY+B*J}},FLinearColor(0,0,0,Op*.7f),3.4f,3);
            P.Line({{CX+A*I,CY+A*J},{CX+B*I,CY+B*J}},Alpha(Kill?Gold:White,Op),1.7f,4);
        }
    }
    const float DamageAge=Now-F.GetLastDamageTime();
    if(DamageAge>=0 && DamageAge<.68f)
    {
        const FVector ToSource=F.GetLastDamageDirection();const float A=1.f-DamageAge/.68f;
        if(!ToSource.IsNearlyZero())
        {
            const float Radians=FMath::DegreesToRadians(ToSource.Rotation().Yaw-Controller.GetControlRotation().Yaw);
            const FVector2f Direction(FMath::Sin(Radians),-FMath::Cos(Radians)),Sideways(-Direction.Y,Direction.X);
            const FVector2f Center(CX,CY),Tip=Center+Direction*43.f,Base=Center+Direction*38.f;
            P.Line({Base-Sideways*8.f,Tip,Base+Sideways*8.f},Alpha(Red,A),3.1f,4);
        }
        P.Box(0,0,P.Width,2,Alpha(Red,A*.75f),1);
    }
}
} // namespace TempleUI

namespace TempleUI
{
void Board(const FPaint& P, const ATempleGameState& Match, const ATemplePlayerState* Local,
           const TArray<FTempleStanding> (&Rosters)[2], int32 Page, int32 Pages, int32 Remaining, bool FromMenu)
{
    const bool bEnd = Match.Phase == 3;
    const uint8 LocalTeam = Local ? Local->Team : 255;
    const int32 LocalId=Local?Local->GetPlayerId():INDEX_NONE;
    const FTempleStanding* FinalPlayer=bEnd?Match.FinalStandings.FindByPredicate(
        [LocalId](const FTempleStanding& Row){return Row.PlayerId==LocalId;}):nullptr;
    const FBoard B(P.Width, P.Height, bEnd);
    P.Box(0, 0, P.Width, P.Height, FLinearColor(.002f,.006f,.007f,.58f));
    P.Box(B.X, B.Y, B.W, B.H, Alpha(Dark,.98f));
    P.Box(B.X, B.Y, B.W, 2, Gold, 1);
    P.Text(B.X+24, B.Y+14, TEXT("TEAM DEATHMATCH"), 10, Gold);

    FString Title = LocalTeam > 1 ? TEXT("Choose a team") : TEXT("Scoreboard");
    FString Detail = FString::Printf(TEXT("First to %d"), Match.ScoreLimit);
    if (bEnd)
    {
        Title = Match.WinnerTeam > 1 ? TEXT("Draw") : !FinalPlayer ? TEXT("Match complete")
                : Match.WinnerTeam == FinalPlayer->Team ? TEXT("Victory") : TEXT("Defeat");
        Detail = Match.WinnerTeam > 1 ? TEXT("Teams tied") : TeamName(Match.WinnerTeam) + TEXT(" WINS");
    }
    P.Text(B.X+23, B.Y+26, Title, 29, White);
    P.Text(B.X+B.W-24, B.Y+16, bEnd ? TEXT("FINAL RESULT") : TEXT("TIME REMAINING"), 10, Muted, true, 1);
    P.Text(B.X+B.W-24, B.Y+37, bEnd ? Detail : Clock(Remaining), 17,
           bEnd ? Side(Match.WinnerTeam) : White, true, 1);
    if (!bEnd) P.Text(B.X+24, B.Y+74, Detail, 11, Muted, false);

    const float Margin = 24, Gap = 23;
    const float ColumnW = (B.W-Margin*2-Gap)*.5f;
    const float HeaderY = B.Y + (bEnd ? 86 : 104);
    for (uint8 Team=0; Team<2; ++Team)
    {
        const float Left = B.X+Margin+Team*(ColumnW+Gap);
        const float Right = Left+ColumnW;
        const FLinearColor Color = Side(Team);
        P.Box(Left, HeaderY, ColumnW, 37, Alpha(Color,.10f));
        P.Box(Left, HeaderY, 3, 37, Color, 1);
        P.Emblem(Left+21, HeaderY+19, 8, Team);
        P.Text(Left+39, HeaderY+7, TeamName(Team)+TEXT(" TEAM"), 14, Color);
        P.Text(Right-10, HeaderY+3, FString::FromInt(Team == 0 ? Match.RedScore : Match.BlueScore), 19, White, true, 1);
        const float LabelsY = HeaderY+44;
        const float KX = Right-77, DX = Right-13;
        P.Text(Left+9, LabelsY, TEXT("PLAYER"), 9, Muted);
        P.Text(KX, LabelsY, TEXT("KILLS"), 9, Muted, true, 1);
        P.Text(DX, LabelsY, TEXT("DEATHS"), 9, Muted, true, 1);
        for (int32 Row=0; Row<RowsPerPage; ++Row)
        {
            const int32 Index = Page*RowsPerPage+Row;
            if (!Rosters[Team].IsValidIndex(Index)) break;
            const FTempleStanding& Entry = Rosters[Team][Index];
            const bool bLocal=Entry.PlayerId==LocalId;
            const float RowY = HeaderY+64+Row*25;
            if (bLocal)
            {
                P.Box(Left, RowY-1, ColumnW, 25, Alpha(Color,.15f));
                P.Box(Left, RowY-1, 2, 25, Color, 1);
            }
            else if (Row%2 == 0) P.Box(Left, RowY-1, ColumnW, 25, Alpha(White,.027f));
            P.Text(Left+9, RowY+2, Entry.Name, 12, bLocal ? Color : White, bLocal, 0, 3, ColumnW-124);
            P.Text(KX, RowY+2, FString::FromInt(Entry.Kills), 12, White, true, 1);
            P.Text(DX, RowY+2, FString::FromInt(Entry.Deaths), 12, Muted, false, 1);
        }
    }
    const float Footer = B.Y+B.H-76;
    P.Box(B.X+24, Footer, B.W-48, 1, Rule, 1);
    if (FinalPlayer)
    {
        const FString Summary = FString::Printf(TEXT("YOUR STATS     %d %s     %d %s     %.2f K/D"),
            FinalPlayer->Kills, FinalPlayer->Kills==1?TEXT("kill"):TEXT("kills"),
            FinalPlayer->Deaths, FinalPlayer->Deaths==1?TEXT("death"):TEXT("deaths"),
            static_cast<double>(FinalPlayer->Kills) / FMath::Max(1,FinalPlayer->Deaths));
        P.Text(B.X+24, Footer-31, Summary, 12, White);
    }
    if (Pages > 1)
        P.Text(B.X+B.W-24, Footer-28, FString::Printf(TEXT("PAGE %d / %d    ·    SCROLL"), Page+1, Pages), 10, Muted, true, 1);
    if (!bEnd && LocalTeam<2 && !FromMenu)
        P.Text(B.X+B.W-24, Footer+29, TEXT("TAB    CLOSE"), 11, Muted, true, 1);
}

void Menu(const FPaint& P,bool Controls,bool Private,ENetMode Mode,const FString& Endpoint,const FString& Feedback)
{
    const FMenu B(P.Width,P.Height,Controls || Private);
    P.Box(0,0,P.Width,P.Height,FLinearColor(.001f,.005f,.006f,.25f));
    P.Box(B.X,B.Y,B.W,B.H,Alpha(Dark,.98f));
    P.Box(B.X,B.Y,B.W,2,Gold,1);
    P.Text(B.X+21,B.Y+18,TEXT("TEAM DEATHMATCH"),10,Gold);
    P.Text(B.X+20,B.Y+36,Controls?TEXT("Controls"):Private?TEXT("Private match"):Mode==NM_Standalone?TEXT("Match paused"):TEXT("Match menu"),25,White);
    if(Private)
    {
        const bool CanHostHere = Mode != NM_Standalone || UTempleGameInstance::SupportsListenServer();
        P.Text(B.X+21,B.Y+90,Mode==NM_Client?TEXT("CONNECTED TO"):CanHostHere?TEXT("HOST ADDRESS"):TEXT("HOSTING"),10,Gold);
        P.Text(B.X+21,B.Y+109,CanHostHere?Endpoint:FString(TEXT("Host from the desktop game.")),16,White);
        if(Mode==NM_Standalone)
        {
            P.Box(B.X+20,B.Y+201,B.W-40,1,Rule,1);
            P.Text(B.X+21,B.Y+216,TEXT("JOIN ANOTHER MATCH"),10,Gold);
        }
        else P.Text(B.X+21,B.Y+151,Mode==NM_Client?TEXT("Leaving returns you to solo play."):
                    TEXT("Share this address with players on the same network."),11,Muted,false);
        P.Text(B.X+20,B.Y+337,Feedback,11,Gold,false,0,3,B.W-40);
        return;
    }
    if(!Controls) return;
    static const TCHAR* Bindings[][2]={
        {TEXT("Move"),TEXT("W A S D   /   Z Q S D")},{TEXT("Look"),TEXT("Mouse")},
        {TEXT("Fire"),TEXT("Left mouse")},{TEXT("Aim"),TEXT("Right mouse")},
        {TEXT("Reload"),TEXT("R")},{TEXT("Jump"),TEXT("Space")},
        {TEXT("Sprint"),TEXT("Left Shift")},{TEXT("Crouch"),TEXT("Left Ctrl")},
        {TEXT("Teams / scoreboard"),TEXT("Hold Tab")},{TEXT("Menu"),TEXT("Esc")}
    };
    for(int32 I=0;I<UE_ARRAY_COUNT(Bindings);++I)
    {
        const float RowY=B.Y+88+I*27;
        if(I%2==0) P.Box(B.X+17,RowY-1,B.W-34,25,Alpha(White,.038f),1);
        P.Text(B.X+24,RowY+1,Bindings[I][0],12,White,false);
        P.Text(B.X+B.W-24,RowY+1,Bindings[I][1],12,Muted,true,1);
    }
}

void Announcement(const FPaint& P, const FString& Label, const FString& Value, FLinearColor Color)
{
    const float X = P.Width*.5f, Y = P.Height*.38f;
    P.Box(X-109,Y-1,218,72,Dark);
    P.Box(X-38,Y-1,76,2,Color,1);
    P.Text(X,Y+9,Label,10,Color,true,.5f);
    P.Text(X,Y+25,Value,22,White,true,.5f);
}
} // namespace TempleUI

UTempleCombatHUD::UTempleCombatHUD(const FObjectInitializer& ObjectInitializer) : Super(ObjectInitializer)
{
    SetIsFocusable(true);
}

void UTempleCombatHUD::NativeOnInitialized()
{
    Super::NativeOnInitialized();
    Actions = WidgetTree->ConstructWidget<UCanvasPanel>(UCanvasPanel::StaticClass(), TEXT("MatchActions"));
    Actions->SetVisibility(ESlateVisibility::SelfHitTestInvisible);
    WidgetTree->RootWidget = Actions;
    SetVisibility(ESlateVisibility::SelfHitTestInvisible);
    RedButton = MakeAction(TEXT("JoinRed"), TEXT("1   Join Red"), TempleUI::Red);
    BlueButton = MakeAction(TEXT("JoinBlue"), TEXT("2   Join Blue"), TempleUI::Blue);
    ReplayButton = MakeAction(TEXT("PlayAgain"), TEXT("Play again"), TempleUI::Gold);
    ResumeButton=MakeAction(TEXT("ResumeGame"),TEXT("Resume"),TempleUI::Gold);
    TeamsButton=MakeAction(TEXT("TeamRoster"),TEXT("Team roster"),TempleUI::Muted);
    ControlsButton=MakeAction(TEXT("ShowControls"),TEXT("Controls"),TempleUI::Muted);
    PrivateButton=MakeAction(TEXT("PrivateMatch"),TEXT("Private match"),TempleUI::Muted);
    HostButton=MakeAction(TEXT("HostMatch"),TEXT("Host this match"),TempleUI::Gold);
    ConnectButton=MakeAction(TEXT("JoinMatch"),TEXT("Join match"),TempleUI::Gold);
    LeaveButton=MakeAction(TEXT("LeaveMatch"),TEXT("Return to solo play"),TempleUI::Muted);
    AddressBox=WidgetTree->ConstructWidget<UEditableTextBox>(UEditableTextBox::StaticClass(),TEXT("HostAddress"));
    AddressBox->SetHintText(FText::FromString(TEXT("Host IPv4 address or address:port")));
    AddressBox->SetSelectAllTextWhenFocused(true);
    auto FieldStyle=AddressBox->GetWidgetStyle();
    FieldStyle.SetBackgroundImageNormal(FSlateColorBrush(FLinearColor(.030f,.047f,.049f,1.f)));
    FieldStyle.SetBackgroundImageHovered(FSlateColorBrush(FLinearColor(.053f,.077f,.079f,1.f)));
    FieldStyle.SetBackgroundImageFocused(FSlateColorBrush(FLinearColor(.080f,.091f,.078f,1.f)));
    FieldStyle.SetForegroundColor(TempleUI::White).SetFocusedForegroundColor(TempleUI::White);
    FieldStyle.SetPadding(FMargin(9,4));
    AddressBox->SetWidgetStyle(FieldStyle);
    AddressBox->SetVisibility(ESlateVisibility::Collapsed);
    Actions->AddChildToCanvas(AddressBox);
    QuitButton=MakeAction(TEXT("QuitDesktop"),TEXT("Quit to desktop"),TempleUI::Muted);
    BackButton=MakeAction(TEXT("MenuBack"),TEXT("Back"),TempleUI::Muted);
    RedButton->OnClicked.AddDynamic(this, &UTempleCombatHUD::JoinRed);
    BlueButton->OnClicked.AddDynamic(this, &UTempleCombatHUD::JoinBlue);
    ReplayButton->OnClicked.AddDynamic(this, &UTempleCombatHUD::Replay);
    ResumeButton->OnClicked.AddDynamic(this,&UTempleCombatHUD::Resume);
    TeamsButton->OnClicked.AddDynamic(this,&UTempleCombatHUD::MenuTeams);
    ControlsButton->OnClicked.AddDynamic(this,&UTempleCombatHUD::MenuControls);
    PrivateButton->OnClicked.AddDynamic(this,&UTempleCombatHUD::MenuPrivate);
    HostButton->OnClicked.AddDynamic(this,&UTempleCombatHUD::HostPrivate);
    ConnectButton->OnClicked.AddDynamic(this,&UTempleCombatHUD::JoinPrivate);
    LeaveButton->OnClicked.AddDynamic(this,&UTempleCombatHUD::LeavePrivate);
    QuitButton->OnClicked.AddDynamic(this,&UTempleCombatHUD::QuitDesktop);
    BackButton->OnClicked.AddDynamic(this,&UTempleCombatHUD::MenuBack);
}

UButton* UTempleCombatHUD::MakeAction(FName Name, const FString& Text, const FLinearColor& Tint)
{
    UButton* Button = WidgetTree->ConstructWidget<UButton>(UButton::StaticClass(),Name);
    UTextBlock* Caption = WidgetTree->ConstructWidget<UTextBlock>();
    Caption->SetText(FText::FromString(Text));
    Caption->SetFont(FCoreStyle::GetDefaultFontStyle("Bold",12));
    Caption->SetColorAndOpacity(FSlateColor(TempleUI::White));
    Caption->SetVisibility(ESlateVisibility::HitTestInvisible);
    Button->SetContent(Caption);
    FButtonStyle Style;
    const FLinearColor Base = TempleUI::Alpha(Tint*.20f,1.f);
    Style.SetNormal(FSlateColorBrush(Base));
    Style.SetHovered(FSlateColorBrush(TempleUI::Alpha(Tint*.37f,1.f)));
    Style.SetPressed(FSlateColorBrush(TempleUI::Alpha(Tint*.51f,1.f)));
    Style.SetDisabled(FSlateColorBrush(TempleUI::Alpha(Tint*.075f,1.f)));
    Style.SetNormalPadding(FMargin(1));
    Style.SetPressedPadding(FMargin(1,2,1,0));
    Button->SetStyle(Style);
    Button->SetVisibility(ESlateVisibility::Collapsed);
    Actions->AddChildToCanvas(Button);
    return Button;
}

TSharedRef<SWidget> UTempleCombatHUD::RebuildWidget()
{
    TSharedRef<SWidget> Controls = Super::RebuildWidget();
    return SNew(SOverlay)
        + SOverlay::Slot() [ SNew(TempleUI::STempleInstruments).OwnerHUD(this) ]
        + SOverlay::Slot() [ Controls ];
}

float UTempleCombatHUD::InterfaceScale(FVector2D Size)
{
    return FMath::Clamp(static_cast<float>(FMath::Min(Size.X/1280.,Size.Y/720.)), .60f, 1.60f);
}

void UTempleCombatHUD::ArrangeActions(const FVector2D& Size, const ATempleGameState* Match,
                                      const ATemplePlayerState* Local, bool bShow, bool bMenu)
{
    const bool bEnd = Match && Match->Phase == 3;
    const uint8 Team = Local ? Local->Team : 255;
    if (!RedButton || (LastSize.Equals(Size,.1) && bShow==bModalOpen && bMenu==bPreviousMenu && bEnd==bPreviousResult && Team==PreviousTeam))
        return;
    bModalOpen=bShow; bPreviousResult=bEnd; bPreviousMenu=bMenu; PreviousTeam=Team; LastSize=Size;
    if(!bMenu){bControlsPage=false;bPrivatePage=false;}
    if(!bShow) bRosterFromMenu=false;
    Actions->SetVisibility(bShow ? ESlateVisibility::Visible : ESlateVisibility::SelfHitTestInvisible);
    const float S=InterfaceScale(Size);
    const TempleUI::FBoard B(Size.X/S,Size.Y/S,bEnd);
    const TempleUI::FMenu M(Size.X/S,Size.Y/S,bControlsPage || bPrivatePage);
    auto Place = [&](UButton* Button, float X, float Y, float Width, float Height, bool bVisible, bool bEnabled=true)
    {
        Button->SetVisibility(bVisible? ESlateVisibility::Visible : ESlateVisibility::Collapsed);
        Button->SetIsEnabled(bEnabled);
        UCanvasPanelSlot* Slot=CastChecked<UCanvasPanelSlot>(Button->Slot);
        Slot->SetPosition(FVector2D(X*S,Y*S));
        Slot->SetSize(FVector2D(Width*S,Height*S));
        CastChecked<UTextBlock>(Button->GetContent())->SetFont(FCoreStyle::GetDefaultFontStyle("Bold",12*S));
    };
    const bool Board=bShow && !bMenu;
    const float Footer=B.Y+B.H-56;
    Place(RedButton,B.X+24,Footer,129,36,Board && !bEnd,Team!=0);
    Place(BlueButton,B.X+161,Footer,129,36,Board && !bEnd,Team!=1);
    Place(ReplayButton,B.X+B.W-171,Footer,147,36,Board && bEnd);
    const bool Main=bMenu && !bControlsPage && !bPrivatePage;
    Place(ResumeButton,M.X+20,M.Y+94,M.W-40,44,Main);
    Place(TeamsButton,M.X+20,M.Y+148,M.W-40,44,Main);
    Place(ControlsButton,M.X+20,M.Y+202,M.W-40,44,Main);
    Place(PrivateButton,M.X+20,M.Y+256,M.W-40,44,Main);
    Place(QuitButton,M.X+20,M.Y+325,M.W-40,44,Main);
    const bool Network=bMenu && bPrivatePage;
    const bool Solo=GetWorld()->GetNetMode()==NM_Standalone;
    Place(HostButton,M.X+20,M.Y+151,M.W-40,36,Network && Solo && UTempleGameInstance::SupportsListenServer(),!bConnecting && !HostAddress.IsEmpty());
    Place(ConnectButton,M.X+20,M.Y+282,M.W-40,36,Network && Solo,!bConnecting);
    Place(LeaveButton,M.X+20,M.Y+203,M.W-40,36,Network && !Solo);
    AddressBox->SetVisibility(Network && Solo?ESlateVisibility::Visible:ESlateVisibility::Collapsed);
    AddressBox->SetIsEnabled(!bConnecting);
    auto* FieldSlot=CastChecked<UCanvasPanelSlot>(AddressBox->Slot);
    FieldSlot->SetPosition(FVector2D((M.X+20)*S,(M.Y+238)*S));
    FieldSlot->SetSize(FVector2D((M.W-40)*S,35*S));
    if(Network && Solo)
    {
        auto Style=AddressBox->GetWidgetStyle();
        Style.TextStyle.SetFont(FCoreStyle::GetDefaultFontStyle("Regular",13*S));
        AddressBox->SetWidgetStyle(Style);
    }
    if(bMenu) Place(BackButton,M.X+20,M.Y+M.H-54,126,35,bControlsPage || bPrivatePage);
    else Place(BackButton,B.X+B.W-(bEnd?302:151),Footer,127,36,Board && bRosterFromMenu);
}

void UTempleCombatHUD::UpdateRoster(const ATempleGameState* Match)
{
    for (auto& TeamRoster : Rosters) TeamRoster.Reset();
    if (!Match) return;
    if(Match->Phase==3)
    {
        for(const FTempleStanding& Row:Match->FinalStandings)
            if(Row.Team<2)Rosters[Row.Team].Add(Row);
    }
    else for (const APlayerState* Entry : Match->PlayerArray)
    {
        const ATemplePlayerState* PS=Cast<ATemplePlayerState>(Entry);
        if (!PS || PS->Team>1) continue;
        Rosters[PS->Team].Emplace(*PS);
    }
    for (auto& TeamRoster : Rosters)
    {
        TeamRoster.Sort([](const FTempleStanding& A,const FTempleStanding& B)
        {
            if(A.Kills!=B.Kills) return A.Kills>B.Kills;
            if(A.Deaths!=B.Deaths) return A.Deaths<B.Deaths;
            return A.Name.Compare(B.Name,ESearchCase::IgnoreCase)<0;
        });
    }
    const int32 Largest=FMath::Max(Rosters[0].Num(),Rosters[1].Num());
    PageCount=FMath::Max(1,FMath::DivideAndRoundUp(Largest,TempleUI::RowsPerPage));
    Page=FMath::Clamp(Page,0,PageCount-1);
}

void UTempleCombatHUD::NativeTick(const FGeometry& Geometry, float DeltaSeconds)
{
    Super::NativeTick(Geometry,DeltaSeconds);
    ATemplePlayerController* PC=Cast<ATemplePlayerController>(GetOwningPlayer());
    UWorld* World=GetWorld();
    if (!PC || !World) return;
    const ATempleGameState* Match=World->GetGameState<ATempleGameState>();
    if (!Match) return;
    const ATemplePlayerState* Local=PC->GetPlayerState<ATemplePlayerState>();
    const ATempleFighter* Fighter=Cast<ATempleFighter>(PC->GetPawn());
    if(auto* Instance=World->GetGameInstance<UTempleGameInstance>();
       Instance && World->GetNetMode()==NM_Standalone && World->GetMapName().Contains(TEXT("L_CanopyDeathmatch")) &&
       (PC->bMenuOpen || (Fighter && Fighter->IsFirstPersonViewSettled())) &&
       Instance->TakeNetworkNotice(NetworkFeedback))
    {
        PC->SetMenuOpen(true);
        bConnecting=false;
        MenuPrivate();
    }
    const float Now=World->GetTimeSeconds();
    if (PreviousPhase==1 && Match->Phase==2) GoUntil=Now+.75f;
    PreviousPhase=Match->Phase;
    if (Fighter)
    {
        if(Fighter!=LastSpawn.Get()) {LastSpawn=PC->GetPawn(); SpawnHintUntil=Now+5.f;}
        const float Kick=FMath::Clamp(1.f-(Now-Fighter->GetLocalShotTime())/.15f,0.f,1.f);
        const float Target=4.f+Fighter->GetVelocity().Size2D()/125.f+Kick*8.f;
        SmoothedSpread=FMath::FInterpTo(SmoothedSpread,Target,DeltaSeconds,15.f);
    }
    const bool Board=PC->bScoreboardVisible || Match->Phase==3 || (Local && Local->Team>1);
    const bool Show=PC->bMenuOpen || Board;
    if (Board && !PC->bMenuOpen && (!bModalOpen || bPreviousMenu || Now>=NextRosterUpdate))
    {
        if(!bModalOpen) Page=0;
        UpdateRoster(Match);
        NextRosterUpdate=Now+.20;
    }
    ArrangeActions(Geometry.GetLocalSize(),Match,Local,Show,PC->bMenuOpen);
}

int32 UTempleCombatHUD::DrawInstruments(const FGeometry& Geometry, FSlateWindowElementList& List, int32 Layer) const
{
    const ATemplePlayerController* PC=Cast<ATemplePlayerController>(GetOwningPlayer());
    UWorld* World=GetWorld();
    if (!PC || !World) return Layer;
    const ATempleGameState* Match=World->GetGameState<ATempleGameState>();
    if(!Match) return Layer;
    const ATemplePlayerState* Local=PC->GetPlayerState<ATemplePlayerState>();
    const ATempleFighter* Fighter=Cast<ATempleFighter>(PC->GetPawn());
    const float Now=World->GetTimeSeconds();
    const double ServerNow=Match->GetServerWorldTimeSeconds();
    const int32 Remaining=Match->RemainingPhaseSeconds(ServerNow);
    const TempleUI::FPaint P(Geometry,List,Layer,InterfaceScale(Geometry.GetLocalSize()));
    if(PC->bMenuOpen)
    {
        TempleUI::ScoreStrip(P,*Match,Remaining);
        TempleUI::Menu(P,bControlsPage,bPrivatePage,World->GetNetMode(),HostAddress,NetworkFeedback);
        return Layer+5;
    }
    if (PC->bScoreboardVisible || Match->Phase==3 || (Local && Local->Team>1))
    {
        TempleUI::Board(P,*Match,Local,Rosters,Page,PageCount,Remaining,bRosterFromMenu);
        return Layer+5;
    }
    const bool bDeploying=Match->Phase==2 && !Fighter && Local && Local->RespawnAt>ServerNow;
    if(bDeploying) P.Box(0,0,P.Width,P.Height,TempleUI::Alpha(TempleUI::Dark,1.f));
    TempleUI::ScoreStrip(P,*Match,Remaining);
    TempleUI::Feed(P,*Match,ServerNow);
    if (Fighter && Fighter->IsAlive())
    {
        TempleUI::Vitals(P,*Fighter,Local ? Local->Team : Fighter->GetTeam());
        if (Match->Phase==2) TempleUI::Aim(P,*Fighter,*PC,Now,SmoothedSpread);
        if(Match->Phase==1 || Now<SpawnHintUntil)
        {
            const float X=P.Width*.5f,Y=P.Height-34;
            P.Box(X-94,Y,188,20,TempleUI::Alpha(TempleUI::Dark,.79f));
            P.Text(X,Y+2,TEXT("TAB   Teams     ·     ESC   Menu"),10,TempleUI::White,true,.5f);
        }
    }
    if (Match->Phase==0) TempleUI::Announcement(P,TEXT("TEAM DEATHMATCH"),TEXT("Waiting for teams"),TempleUI::Gold);
    else if (Match->Phase==1)
        TempleUI::Announcement(P,TEXT("MATCH STARTS IN"),FString::FromInt(FMath::Max(1,Remaining)),TempleUI::Gold);
    else if (Local && Local->RespawnAt>ServerNow && (!Fighter || !Fighter->IsAlive()))
    {
        const double Seconds=FMath::Min(static_cast<double>(Match->RespawnDelay),Local->RespawnAt-ServerNow);
        const int32 DisplaySeconds=FMath::Max(1,static_cast<int32>(FMath::CeilToInt(Seconds-.001)));
        const FString Label=bDeploying ? TempleUI::TeamName(Local->Team)+TEXT(" TEAM") : TEXT("ELIMINATED");
        const FString Detail=FString::Printf(TEXT("%s in %d"),bDeploying?TEXT("Deploying"):TEXT("Respawn"),DisplaySeconds);
        TempleUI::Announcement(P,Label,Detail,TempleUI::Side(Local->Team));
    }
    else if (Now<GoUntil)
        TempleUI::Announcement(P,TEXT("TEAM DEATHMATCH"),TEXT("Go"),TempleUI::Gold);
    return Layer+5;
}

void UTempleCombatHUD::TurnPage(int32 Delta) { Page=FMath::Clamp(Page+Delta,0,PageCount-1); }

FReply UTempleCombatHUD::NativeOnPreviewKeyDown(const FGeometry& Geometry,const FKeyEvent& Event)
{
    if (bModalOpen && !Event.IsRepeat())
    {
        const FKey Key=Event.GetKey();
        if(bPreviousMenu)
        {
            if(Key==EKeys::Escape) { if(bControlsPage || bPrivatePage) MenuBack(); else Resume(); return FReply::Handled(); }
            if(bPrivatePage && Key==EKeys::Enter && AddressBox->HasKeyboardFocus() && !bConnecting)
                {JoinPrivate();return FReply::Handled();}
            return Super::NativeOnPreviewKeyDown(Geometry,Event);
        }
        if (Key==EKeys::One && !bPreviousResult) { JoinRed(); return FReply::Handled(); }
        if (Key==EKeys::Two && !bPreviousResult) { JoinBlue(); return FReply::Handled(); }
        if (Key==EKeys::Enter && bPreviousResult) { Replay(); return FReply::Handled(); }
        if (Key==EKeys::PageUp || Key==EKeys::PageDown)
        {
            TurnPage(Key==EKeys::PageUp?-1:1); return FReply::Handled();
        }
        if (Key==EKeys::Escape && !bPreviousResult && PreviousTeam<2)
        {
            if (bRosterFromMenu) MenuBack();
            else if (auto* PC=Cast<ATemplePlayerController>(GetOwningPlayer())) PC->SetScoreboardVisible(false);
            return FReply::Handled();
        }
    }
    return Super::NativeOnPreviewKeyDown(Geometry,Event);
}

FReply UTempleCombatHUD::NativeOnKeyUp(const FGeometry& Geometry,const FKeyEvent& Event)
{
    if (Event.GetKey()==EKeys::Tab && bModalOpen && !bPreviousMenu && !bRosterFromMenu)
    {
        if (auto* PC=Cast<ATemplePlayerController>(GetOwningPlayer())) PC->SetScoreboardVisible(false);
        return FReply::Handled();
    }
    return Super::NativeOnKeyUp(Geometry,Event);
}

FReply UTempleCombatHUD::NativeOnMouseWheel(const FGeometry& Geometry,const FPointerEvent& Event)
{
    if (bModalOpen && !bPreviousMenu && PageCount>1)
    {
        TurnPage(Event.GetWheelDelta()>0?-1:1); return FReply::Handled();
    }
    return Super::NativeOnMouseWheel(Geometry,Event);
}

FReply UTempleCombatHUD::NativeOnMouseButtonDown(const FGeometry& Geometry,const FPointerEvent& Event)
{
    return bModalOpen ? FReply::Handled() : Super::NativeOnMouseButtonDown(Geometry,Event);
}

FReply UTempleCombatHUD::NativeOnMouseButtonUp(const FGeometry& Geometry,const FPointerEvent& Event)
{
    return bModalOpen ? FReply::Handled() : Super::NativeOnMouseButtonUp(Geometry,Event);
}

void UTempleCombatHUD::JoinRed()
{
    if(auto* PC=Cast<ATemplePlayerController>(GetOwningPlayer())) PC->JoinTeam(0);
}

void UTempleCombatHUD::JoinBlue()
{
    if(auto* PC=Cast<ATemplePlayerController>(GetOwningPlayer())) PC->JoinTeam(1);
}

void UTempleCombatHUD::Replay()
{
    if(auto* PC=Cast<ATemplePlayerController>(GetOwningPlayer())) PC->ReplayMatch();
}

void UTempleCombatHUD::Resume()
{
    bControlsPage=false; bPrivatePage=false; bRosterFromMenu=false;
    if(auto* PC=Cast<ATemplePlayerController>(GetOwningPlayer())) PC->SetMenuOpen(false);
}

void UTempleCombatHUD::MenuTeams()
{
    bRosterFromMenu=true;
    if(auto* PC=Cast<ATemplePlayerController>(GetOwningPlayer())) PC->OpenTeamsFromMenu();
}

void UTempleCombatHUD::MenuControls()
{
    bControlsPage=true;
    LastSize=FVector2D::ZeroVector;
}

void UTempleCombatHUD::MenuPrivate()
{
    bPrivatePage=true;
    if(auto* Instance=GetWorld()->GetGameInstance<UTempleGameInstance>())
    {
        HostAddress=GetWorld()->GetNetMode()==NM_Standalone?Instance->SuggestedHostEndpoint():Instance->CurrentEndpoint();
        if(AddressBox->GetText().IsEmpty() && !Instance->LastJoinedEndpoint().IsEmpty())
            AddressBox->SetText(FText::FromString(Instance->LastJoinedEndpoint()));
    }
    LastSize=FVector2D::ZeroVector;
}
void UTempleCombatHUD::HostPrivate()
{
    if(auto* Instance=GetWorld()->GetGameInstance<UTempleGameInstance>())
        if(Instance->HostPrivateMatch(NetworkFeedback))HostAddress=Instance->CurrentEndpoint();
    LastSize=FVector2D::ZeroVector;
}
void UTempleCombatHUD::JoinPrivate()
{
    if(auto* Instance=GetWorld()->GetGameInstance<UTempleGameInstance>())
        bConnecting=Instance->JoinPrivateMatch(AddressBox->GetText().ToString(),NetworkFeedback);
    LastSize=FVector2D::ZeroVector;
}
void UTempleCombatHUD::LeavePrivate()
{
    if(auto* Instance=GetWorld()->GetGameInstance<UTempleGameInstance>())Instance->LeavePrivateMatch();
}

void UTempleCombatHUD::MenuBack()
{
    bControlsPage=false; bPrivatePage=false; bRosterFromMenu=false;
    LastSize=FVector2D::ZeroVector;
    if(auto* PC=Cast<ATemplePlayerController>(GetOwningPlayer()))
        if(!PC->bMenuOpen) PC->SetMenuOpen(true);
}

void UTempleCombatHUD::QuitDesktop()
{
    if(auto* PC=Cast<ATemplePlayerController>(GetOwningPlayer())) PC->QuitGame();
}
