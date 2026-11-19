#if WITH_EDITOR
#include "Animation/AnimBlueprint.h"
#include "Animation/AnimSequence.h"
#include "AnimGraphNode_LayeredBoneBlend.h"
#include "AnimGraphNode_ComponentToLocalSpace.h"
#include "AnimGraphNode_LocalToComponentSpace.h"
#include "AnimGraphNode_Root.h"
#include "AnimGraphNode_TwoBoneIK.h"
#include "AnimGraphNode_SequencePlayer.h"
#include "AnimGraphNode_Slot.h"
#include "EdGraph/EdGraph.h"
#include "EdGraph/EdGraphPin.h"
#include "HAL/IConsoleManager.h"
#include "Kismet2/BlueprintEditorUtils.h"
#include "Kismet2/KismetEditorUtilities.h"

namespace
{
void FitSupportHand(UAnimGraphNode_Slot* Slot,UAnimBlueprint* Blueprint)
{
    UEdGraph* Graph=Slot->GetGraph();
    UEdGraphPin* SlotIn=Slot->FindPin(TEXT("Source"),EGPD_Input);
    if (!SlotIn || SlotIn->LinkedTo.IsEmpty()) return;
    UEdGraphPin* Source=SlotIn->LinkedTo[0];
    if (Source->GetOwningNode()->IsA<UAnimGraphNode_ComponentToLocalSpace>()) return;
    Graph->Modify();
    FGraphNodeCreator<UAnimGraphNode_LocalToComponentSpace> MakeCS(*Graph);
    auto* CS=MakeCS.CreateNode(false);
    CS->NodePosX=Slot->NodePosX-660; CS->NodePosY=Slot->NodePosY+130;
    MakeCS.Finalize();
    FGraphNodeCreator<UAnimGraphNode_TwoBoneIK> MakeIK(*Graph);
    auto* IK=MakeIK.CreateNode(false);
    IK->NodePosX=Slot->NodePosX-470; IK->NodePosY=CS->NodePosY;
    IK->Node.IKBone.BoneName=TEXT("hand_l");
    IK->Node.EffectorLocationSpace=BCS_BoneSpace;
    IK->Node.EffectorTarget=FBoneSocketTarget(TEXT("HandGrip_R"),true);
    // The authored support locator is (0,28.52,3) on the rifle. The wrist lies behind and to the left of the palm.
    IK->Node.EffectorLocation=FVector(5.3,21,6.2);
    IK->Node.JointTargetLocationSpace=BCS_BoneSpace;
    IK->Node.JointTarget=FBoneSocketTarget(TEXT("lowerarm_l"));
    IK->Node.JointTargetLocation=FVector::ZeroVector;
    MakeIK.Finalize();
    if (auto* Goal=IK->FindPin(TEXT("EffectorLocation"),EGPD_Input)) Goal->DefaultValue=TEXT("5.3,21,6.2");
    FGraphNodeCreator<UAnimGraphNode_ComponentToLocalSpace> MakeLS(*Graph);
    auto* LS=MakeLS.CreateNode(false);
    LS->NodePosX=Slot->NodePosX-215; LS->NodePosY=CS->NodePosY;
    MakeLS.Finalize();
    SlotIn->BreakAllPinLinks();
    Source->MakeLinkTo(CS->FindPinChecked(TEXT("LocalPose"),EGPD_Input));
    CS->FindPinChecked(TEXT("ComponentPose"),EGPD_Output)->MakeLinkTo(IK->FindPinChecked(TEXT("ComponentPose"),EGPD_Input));
    IK->FindPinChecked(TEXT("Pose"),EGPD_Output)->MakeLinkTo(LS->FindPinChecked(TEXT("ComponentPose"),EGPD_Input));
    LS->FindPinChecked(TEXT("Pose"),EGPD_Output)->MakeLinkTo(SlotIn);
    FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(Blueprint);
    FKismetEditorUtilities::CompileBlueprint(Blueprint);
    Blueprint->MarkPackageDirty();
    UE_LOG(LogTemp,Display,TEXT("Temple support hand fitted before the upper-body action slot in %s"),*Blueprint->GetName());
}

void AuthorPose(UAnimBlueprint* Blueprint, bool bView)
{
    if (!Blueprint) return;
    TArray<UEdGraph*> Graphs;
    Blueprint->GetAllGraphs(Graphs);
    for (UEdGraph* Graph : Graphs)
    {
        if (Graph->GetFName()!=TEXT("AnimGraph")) continue;
        for (UEdGraphNode* Node : Graph->Nodes)
            if (auto* Slot=Cast<UAnimGraphNode_Slot>(Node)) { FitSupportHand(Slot,Blueprint); return; }
        UEdGraphPin* Target=nullptr;
        for (UEdGraphNode* Node : Graph->Nodes)
        {
            if (!Node) continue;
            for (UEdGraphPin* Pin : Node->Pins)
            {
                if (!Pin || Pin->Direction!=EGPD_Input) continue;
                if (bView && Node->IsA<UAnimGraphNode_Root>() && Pin->PinName==TEXT("Result")) Target=Pin;
                if (!bView && Node->IsA<UAnimGraphNode_LayeredBoneBlend>() &&
                    Pin->PinName.ToString().StartsWith(TEXT("BlendPoses")) && Pin->LinkedTo.Num()) Target=Pin;
            }
        }
        if (!Target)
        {
            UE_LOG(LogTemp,Error,TEXT("Temple pose authoring could not locate input in %s"),*Blueprint->GetName());
            return;
        }
        Graph->Modify();
        UEdGraphPin* Base=nullptr;
        if (bView)
        {
            FGraphNodeCreator<UAnimGraphNode_SequencePlayer> CreateBase(*Graph);
            auto* Player=CreateBase.CreateNode(false);
            UAnimSequence* Idle=LoadObject<UAnimSequence>(nullptr,TEXT("/Game/Characters/Mannequins/Anims/Rifle/MF_Rifle_Idle_ADS.MF_Rifle_Idle_ADS"));
            Player->Node.SetSequence(Idle);
            Player->NodePosX=Target->GetOwningNode()->NodePosX-510;
            Player->NodePosY=Target->GetOwningNode()->NodePosY;
            CreateBase.Finalize();
            Base=Player->FindPin(TEXT("Pose"),EGPD_Output);
        }
        else Base=Target->LinkedTo[0];
        if (!Base) return;
        FGraphNodeCreator<UAnimGraphNode_Slot> CreateSlot(*Graph);
        auto* Slot=CreateSlot.CreateNode(false);
        Slot->Node.SlotName=TEXT("DefaultSlot");
        Slot->Node.bAlwaysUpdateSourcePose=true;
        Slot->NodePosX=Target->GetOwningNode()->NodePosX-210;
        Slot->NodePosY=Target->GetOwningNode()->NodePosY+70;
        CreateSlot.Finalize();
        UEdGraphPin* SlotIn=Slot->FindPin(TEXT("Source"),EGPD_Input);
        UEdGraphPin* SlotOut=Slot->FindPin(TEXT("Pose"),EGPD_Output);
        if (!SlotIn || !SlotOut) return;
        Target->BreakAllPinLinks();
        Base->MakeLinkTo(SlotIn);
        SlotOut->MakeLinkTo(Target);
        FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(Blueprint);
        FKismetEditorUtilities::CompileBlueprint(Blueprint);
        Blueprint->MarkPackageDirty();
        UE_LOG(LogTemp,Display,TEXT("Temple pose graph %s slot input %s, output %s (%s)"),*Blueprint->GetName(),
            *Base->GetOwningNode()->GetName(),*Target->GetOwningNode()->GetName(),*Target->PinName.ToString());
        FitSupportHand(Slot,Blueprint);
        return;
    }
}
void AuthorCombatPoses()
{
    AuthorPose(LoadObject<UAnimBlueprint>(nullptr,TEXT("/Game/TempleTDM/Animation/ABP_TempleArms.ABP_TempleArms")),true);
    AuthorPose(LoadObject<UAnimBlueprint>(nullptr,TEXT("/Game/TempleTDM/Animation/ABP_TempleBody.ABP_TempleBody")),false);
}
FAutoConsoleCommand BuildPoses(TEXT("Temple.AuthorCombatPoses"),TEXT("Compile the editable combat animation slots."),FConsoleCommandDelegate::CreateStatic(&AuthorCombatPoses));
}
#endif
