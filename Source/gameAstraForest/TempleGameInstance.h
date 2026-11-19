#pragma once

#include "Engine/GameInstance.h"
#include "Engine/LocalPlayer.h"
#include "IpNetDriver.h"
#include "TempleGameInstance.generated.h"

UCLASS()
class GAMEASTRAFOREST_API UTempleGameInstance : public UGameInstance
{
    GENERATED_BODY()

public:
    virtual void Init() override;
    virtual void Shutdown() override;
    virtual void StartGameInstance() override;
    virtual void LoadComplete(float LoadTime, const FString& MapName) override;
    static bool SupportsListenServer();
    FString SuggestedHostEndpoint() const;
    FString CurrentEndpoint() const;
    const FString& LastJoinedEndpoint() const { return LastHost; }
    bool HostPrivateMatch(FString& Feedback);
    bool JoinPrivateMatch(const FString& Address, FString& Feedback);
    void LeavePrivateMatch();
    bool TakeNetworkNotice(FString& Feedback);
private:
    void NetworkFailed(UWorld* World, UNetDriver* Driver, ENetworkFailure::Type Failure, const FString& Detail);
    FString NetworkNotice;
    FString LastHost;
    bool bJoiningFromMenu = false;
};

/** Bind a menu-hosted game to the selected local adapter. Other worlds use the engine defaults. */
UCLASS(Transient, Config=Engine)
class GAMEASTRAFOREST_API UTempleNetDriver : public UIpNetDriver
{
    GENERATED_BODY()
public:
    virtual bool InitListen(FNetworkNotify* InNotify,FURL& LocalURL,bool bReuse,FString& Error) override;
protected:
    virtual FUniqueSocket CreateAndBindSocket(TSharedRef<FInternetAddr> BindAddr,int32 Port,bool bReuse,
        int32 RecvSize,int32 SendSize,FString& Error) override;
private:
    TSharedPtr<FInternetAddr> HostAdapter;
};

UCLASS()
class GAMEASTRAFOREST_API UTempleLocalPlayer : public ULocalPlayer
{
    GENERATED_BODY()

public:
    virtual FString GetNickname() const override;
};
