#include "TempleGameInstance.h"
#include "GameFramework/PlayerController.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "HAL/IConsoleManager.h"
#include "Interfaces/IPv4/IPv4Address.h"
#include "IPAddress.h"
#include "Kismet/GameplayStatics.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"

#if defined(PLATFORM_WASM) && PLATFORM_WASM
#include "Engine/PostProcessVolume.h"
#include "EngineUtils.h"
#include "UObject/Package.h"
#endif

namespace
{
bool PrivateAddress(const FString& Text)
{
    FIPv4Address IP;
    return FIPv4Address::Parse(Text,IP) && IP.ToString()==Text &&
           (IP.IsSiteLocalAddress() || IP.IsLoopbackAddress() || IP.IsLinkLocal());
}

int32 MatchPort()
{
    int32 Port=FURL::UrlConfig.DefaultPort;
    FParse::Value(FCommandLine::Get(),TEXT("Port="),Port);
    return Port;
}

FString LocalMatchAddress()
{
    FString Bound;
    if(FParse::Value(FCommandLine::Get(),TEXT("MULTIHOME="),Bound))
        return PrivateAddress(Bound)?Bound:FString();
    TArray<TSharedPtr<FInternetAddr>> Addresses;
    auto* Sockets=ISocketSubsystem::Get(PLATFORM_SOCKETSUBSYSTEM);
    if(Sockets && Sockets->GetLocalAdapterAddresses(Addresses))
        for(const auto& Address:Addresses)
            if(Address && PrivateAddress(Address->ToString(false)) && !Address->ToString(false).StartsWith(TEXT("127.")))
                return Address->ToString(false);
    return TEXT("127.0.0.1");
}
}

bool UTempleGameInstance::SupportsListenServer()
{
    static const IConsoleVariable* Setting = IConsoleManager::Get().FindConsoleVariable(TEXT("net.SupportsListenServers"));
    return !Setting || Setting->GetBool();
}

bool UTempleNetDriver::InitListen(FNetworkNotify* InNotify,FURL& URL,bool bReuse,FString& Error)
{
    if(const TCHAR* Adapter=URL.GetOption(TEXT("CanopyBind="),nullptr))
    {
        if(!PrivateAddress(Adapter)){Error=TEXT("Invalid local interface.");return false;}
        HostAdapter=GetSocketSubsystem()->CreateInternetAddr(FNetworkProtocolTypes::IPv4);
        bool Valid=false;
        HostAdapter->SetIp(Adapter,Valid);
        if(!Valid){Error=TEXT("Invalid local interface.");return false;}
    }
    return Super::InitListen(InNotify,URL,bReuse,Error);
}

FUniqueSocket UTempleNetDriver::CreateAndBindSocket(TSharedRef<FInternetAddr> BindAddr,int32 Port,bool bReuse,
    int32 RecvSize,int32 SendSize,FString& Error)
{
    return Super::CreateAndBindSocket(HostAdapter?HostAdapter.ToSharedRef():BindAddr,Port,bReuse,RecvSize,SendSize,Error);
}

void UTempleGameInstance::Init()
{
    Super::Init();
    if(GEngine)GEngine->OnNetworkFailure().AddUObject(this,&UTempleGameInstance::NetworkFailed);
}
void UTempleGameInstance::Shutdown()
{
    if(GEngine)GEngine->OnNetworkFailure().RemoveAll(this);
    Super::Shutdown();
}

void UTempleGameInstance::LoadComplete(float LoadTime, const FString& MapName)
{
    Super::LoadComplete(LoadTime, MapName);
#if defined(PLATFORM_WASM) && PLATFORM_WASM
    UWorld* World = GetWorld();
    if (!World || World->GetPackage()->GetFName() != TEXT("/Game/AstraTemple/Maps/L_CanopyDeathmatch"))
        return;

    // The mobile WebGPU renderer needs more exposure for the temple's fixed daylight setup.
    for (TActorIterator<APostProcessVolume> It(World); It; ++It)
    {
        if (It->bUnbound && It->Settings.bOverride_AutoExposureBias)
            It->Settings.AutoExposureBias += 2.65f;
    }
#endif
}

FString UTempleGameInstance::SuggestedHostEndpoint() const
{
    if (!SupportsListenServer()) return {};
    const FString Address=LocalMatchAddress();
    return Address.IsEmpty()?FString():FString::Printf(TEXT("%s:%d"),*Address,MatchPort());
}
FString UTempleGameInstance::CurrentEndpoint() const
{
    UWorld* World=GetWorld();
    if(!World || !World->GetNetDriver())return {};
    auto* Driver=World->GetNetDriver();
    if(World->GetNetMode()==NM_Client)
        return FString::Printf(TEXT("%s:%d"),*World->URL.Host,World->URL.Port);
    const auto Bound=Driver->GetLocalAddr();
    return Bound?Bound->ToString(true):FString();
}
bool UTempleGameInstance::HostPrivateMatch(FString& Feedback)
{
    if (!SupportsListenServer())
    {
        Feedback = TEXT("Host the match from the desktop game.");
        return false;
    }
    UWorld* World=GetWorld();
    const FString Address=LocalMatchAddress();
    const int32 Port=MatchPort();
    if(!World || World->GetNetMode()!=NM_Standalone || Address.IsEmpty() || Port<1 || Port>65535)
    {
        Feedback=TEXT("Choose an available local network interface.");
        return false;
    }
    FURL URL=World->URL;
    URL.Port=Port;
    URL.AddOption(*FString::Printf(TEXT("CanopyBind=%s"),*Address));
    if(!World->Listen(URL))
    {
        Feedback=FString::Printf(TEXT("Could not host on port %d. Check that it is free."),Port);
        return false;
    }
    if(auto* Player=GetFirstLocalPlayerController())Player->SetPause(false);
    Feedback=TEXT("Your match is open.");
    return true;
}
bool UTempleGameInstance::JoinPrivateMatch(const FString& Input,FString& Feedback)
{
    const FString Trimmed=Input.TrimStartAndEnd();
    FString Address=Trimmed,PortString;
    int32 Port=MatchPort();
    if(Trimmed.Split(TEXT(":"),&Address,&PortString))
    {
        Port=FCString::Atoi(*PortString);
        if(FString::FromInt(Port)!=PortString)Port=0;
    }
    auto* Player=GetFirstLocalPlayerController();
    if(!Player || GetWorld()->GetNetMode()!=NM_Standalone || !PrivateAddress(Address) || Port<1 || Port>65535)
    {
        Feedback=TEXT("Enter a private IPv4 address and a valid port.");
        return false;
    }
    bJoiningFromMenu=true;
    NetworkNotice.Reset();
    Feedback=TEXT("Connecting to the host…");
    LastHost=FString::Printf(TEXT("%s:%d"),*Address,Port);
    Player->ClientTravel(LastHost,TRAVEL_Absolute);
    return true;
}
void UTempleGameInstance::LeavePrivateMatch()
{
    bJoiningFromMenu=false;
    NetworkNotice.Reset();
    UGameplayStatics::OpenLevel(this,TEXT("/Game/AstraTemple/Maps/L_CanopyDeathmatch"),true);
}
void UTempleGameInstance::NetworkFailed(UWorld* World,UNetDriver* Driver,ENetworkFailure::Type Failure,const FString& Detail)
{
    if(!bJoiningFromMenu || (World && World!=GetWorld()))return;
    bJoiningFromMenu=false;
    if(Detail.Contains(TEXT("full"),ESearchCase::IgnoreCase))NetworkNotice=TEXT("The match is full.");
    else if(Failure==ENetworkFailure::OutdatedClient || Failure==ENetworkFailure::OutdatedServer)
        NetworkNotice=TEXT("Both players need the same game version.");
    else if(Driver && Driver->NetDriverName==NAME_PendingNetDriver)
        NetworkNotice=TEXT("Host unavailable. Check the address and port.");
    else NetworkNotice=TEXT("Connection lost. Rejoin when the host returns.");
}
bool UTempleGameInstance::TakeNetworkNotice(FString& Feedback)
{
    if(NetworkNotice.IsEmpty())return false;
    Feedback=MoveTemp(NetworkNotice);
    NetworkNotice.Reset();
    return true;
}

FString UTempleLocalPlayer::GetNickname() const
{
    FString RequestedName;
    if (!FParse::Value(FCommandLine::Get(), TEXT("TempleName="), RequestedName))
    {
        FParse::Value(FCommandLine::Get(), TEXT("?Name="), RequestedName);
    }
    int32 NextOption;
    if (RequestedName.FindChar(TEXT('?'), NextOption))
    {
        RequestedName.LeftInline(NextOption);
    }
    RequestedName.TrimStartAndEndInline();
    if (!RequestedName.IsEmpty())
    {
        return RequestedName.Left(20);
    }
    return FParse::Param(FCommandLine::Get(), TEXT("TempleJoin")) ? TEXT("Ranger") : TEXT("Pathfinder");
}

void UTempleGameInstance::StartGameInstance()
{
    const bool bHost = FParse::Param(FCommandLine::Get(), TEXT("TempleHost"));
    const bool bJoin = FParse::Param(FCommandLine::Get(), TEXT("TempleJoin"));
    bool bLocalSession = bHost != bJoin;
    int32 Port = 7777;
    if (bLocalSession)
    {
        FString BindingAddress;
        if (FParse::Value(FCommandLine::Get(), TEXT("MULTIHOME="), BindingAddress))
        {
            bLocalSession = BindingAddress == TEXT("127.0.0.1");
        }
        else
        {
            FCommandLine::Append(TEXT(" -MULTIHOME=127.0.0.1"));
        }
        FParse::Value(FCommandLine::Get(), TEXT("Port="), Port);
        bLocalSession = bLocalSession && Port > 0 && Port <= 65535;
    }

    Super::StartGameInstance();

    if (bLocalSession && bHost && SupportsListenServer())
    {
        EnableListenServer(true, Port);
    }
    else if (bLocalSession && bJoin)
    {
        if (APlayerController* Player = GetFirstLocalPlayerController())
        {
            Player->ClientTravel(FString::Printf(TEXT("127.0.0.1:%d"), Port), TRAVEL_Absolute);
        }
    }
}
