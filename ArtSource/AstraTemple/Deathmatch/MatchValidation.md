# Canopy Clash

Launch [the Windows game](../../../Builds/Windows/gameAstraForest.exe), or open [the Unreal project](../../../gameAstraForest.uproject) and press Play on its default level, `L_CanopyDeathmatch`. A solo player joins four allies against five opponents on the grounds of the Temple of the Canopy. Open the roster to choose Red or Blue. The first team to 50 wins. At ten minutes the higher score wins and equal scores produce a draw. The results screen offers a new match on the same map.

The Windows build starts in solo play. To play together on a private network, the host opens **Escape → Private match → Host this match** and shares the address displayed there. Other players open **Private match**, enter that address and choose **Join match**. Joining during a round takes an available bot place. **Return to solo play** leaves the session.

To explore the original temple in the editor, open `/Game/AstraTemple/Maps/L_TempleOfTheCanopy`. [Exploration routes and viewpoints](../validation_report.md)

| Action | Desktop control |
|---|---|
| Walk and look | WASD, ZQSD or arrow keys and mouse |
| Jump, sprint, crouch | Space, hold Left Shift, hold Left Ctrl |
| Fire, aim, reload | Hold left mouse, hold right mouse, R |
| Roster and teams | Hold Tab. Choose a team by button or number key |
| Game menu | Escape |
| Replay after the result | Play again or Enter |

## Arena and rules

The Roots Gate and East Quay each have six player starts, a woven team standard and stone cover. The central causeway offers the shortest crossing. The forest gallery passes the Lower Ford shrine. The western cloister crosses a two-arch bridge at the spring and gives Red a route to the elevated temple without crossing Blue's deployment area. Three paving stones form a walkable intermediate step at the south edge of the quay. The original exploration level remains in the project. [Native navigation paths](ArenaNavigation.json) · [Western spring crossing](Review/WestCrossing.png) · [South quay steps](Review/SouthQuayBeforeAfter.jpg)

The reference arena is the Epic shooter template's `Lvl_ArenaShooter`. Its six starts, two NPC spawners, five elevated jump pads and 29.4 × 33.5 m navigation volume informed the distributed starts, alternate routes and change of elevation. The temple retains its existing stairs and causeways. [Reference arena inspection through Unreal MCP](ArenaStudy.json)

The runtime uses Epic's existing rigged character family and rifle assets. Fab listed both personal and professional licenses for the character pack as free. The team standards, their marks and textile material are original to this mode. [Mannequins Asset Pack on Fab](https://www.fab.com/listings/ad542ee6-34d0-4828-a56c-13846cd649d0)

Set team size, time, score target, respawn delay, temporary protection and friendly fire in the `TempleMatchMode` section of [DefaultGame.ini](../../../Config/DefaultGame.ini). At the default settings a fresh player has 100 health and 30/120 ammunition. The shield lasts 2.75 seconds and ends on the first shot. Crossing into the opposing base returns the intruder to a friendly start. A defender who fires from home can draw return fire from an opponent with a clear view for six seconds. [Live spawn and movement checks](SpawnGameplay.json) · [Damage and protection checks](ProtectionAndDamage.json)

## Desktop playtests

| Test | Observed in Unreal |
|---|---|
| Movement and aim | The mapped WASD, ZQSD and arrow keys moved in the expected directions. Walking reached 5.10 m/s, sprinting 6.90 m/s and crouching 2.35 m/s. The jump reached 1.13 m before landing. ADS interpolated from 90° to 64°. Three shots fired into a gate wall consumed three rounds and left the opponent behind it at full health. |
| Replicated combat | Two independent clients saw the same health changes from direct carbine hits. Body and head hits dealt 24 and 48 damage. The server credited the attacker once and returned the victim with full health and temporary protection after about three seconds. |
| Quick turns and cover | After an 85° turn and a shot in the same frame, the remote target lost 24 health under 182 ms measured latency. At the quay, the blue player could see an opponent 4.86 m away around a stone screen. The first shot hit the screen 1.26 m from the muzzle. Moving 19 cm sideways cleared the muzzle and the next round hit. |
| Input latency | At 112.5 ms simulated round-trip latency the first local flash followed the click by 14.2 ms. Ammo updated on server confirmation. The shooter received 36 flashes for 36 accepted shots across a tap, a burst and a magazine. |
| Muzzle flash | In a rendered 1280 × 720 game the flash emitter stayed on the projected barrel socket throughout 28 samples of firing, including sideways movement, turning, aiming and a three-shot burst. At 33 ms the previous effect could be 373 pixels away while strafing and turning in ADS. The third-person flash follows the world rifle's socket. |
| Audio | The native stereo mixer recorded distinct stone and forest footfalls. Walking footsteps were about 0.37 seconds apart. Crouching increased this to 0.50 seconds. An immobile listener heard a moving remote player switch sides across the stereo field. |
| Opponent perception | Behind a masonry column the bot ignored a visible ally and lost sight of the opponent. It pursued the last seen position and stopped firing after the next visibility update. |
| Repeated matches | An instrumented cooked Windows game completed eight match endings and eight restarts. Each post-collection sample contained ten current fighters, nine AI controllers, one HUD and zero retired fighters. |
| Private matches | Two Unreal game instances joined through the private-match menu on this PC's Ethernet address. The default match accepted a playable host and nine guests, five on each team. The eleventh player received “Server full.” A bot filled one departing player’s place and yielded it on reconnection. The reconnect test also covered a closed port and a lost host. A second physical PC was unavailable for this test. |
| Match results | A player joining after the final elimination saw the same frozen standings as the host. That player entered the roster on replay. With the score ceiling raised to exercise the clock, a match ended at exactly 600 seconds. Equal scores produced a draw with a working replay action. |
| Changing teams | A live team transfer uses the normal three-second deployment delay. The first frame after the new pawn appeared had a camera-to-eye error of 0.000 cm. Clicking Play again also placed the camera at the new spawn in the same frame. |
| Protected routes | The Red ranger reached the temple landing from East Quay in 11.87 seconds, from the ford in 13.03 seconds and from West Plaza in 9.30 seconds. All three paths stayed outside Blue's deployment area. Both teams could enter and leave their own base. An opponent who fired from cover became visible when exposed and stopped drawing fire after breaking line of sight. [Movement and perception measurements](Review/DeploymentRoutes.json) |

The server owns damage, team scores, ammunition and the final result. Unreal handles character movement prediction on each client. The camera, HUD and immediate feedback for the shooter's own input also run locally. [Gameplay measurements](Review/GameplayChecks.json) · [Saved rules and native classes](Review/SavedArena.json) · [Default map and Unreal MCP on a fresh editor launch](Review/FreshEditor.json)

## Release playtests

Forty five-on-five bot matches on the delivered map ran for 165.4 minutes of active match time across four seeds. Red won 27 games and Blue won 13. They scored 1,955 and 1,860 eliminations respectively. The median final margin was four points, and 16 games finished within three points. The median engagement distance was 39.2 m. [Results by game and seed](Review/BalanceReport.json) · [Movement and eliminations](Review/ArenaActivity.png)

The bots travelled 323 km during those 40 matches and recorded zero five-second movement stalls or forced safety returns. On the earlier map a bot spent 35 seconds trying to climb a 48.4° face at the West Spring escarpment. A local navigation exclusion now redirects it onto walkable ground. All 15 targeted crossings passed. The ranger also completed 28 traversal runs, covering 1,282 m in 70 legs. [Escarpment diagnosis and retest](Review/WestSpringNavigation.json) · [Ranger traversal](Review/RangerTraversal.json)

A Windows Shipping host finished a private match 50–47 with two player slots occupied and eight bots. A remote client requested the replay. Both teams returned to zero and the next elimination counted in the new round.

All 19 private-menu checks passed on the packaged game content, including hosting, joining, leaving, losing the host and reconnecting to the saved address. [Network match and private-menu results](Review/GameplayChecks.json)

On a GeForce RTX 3080 and Core i7-10700KF, the native D3D12 Development game averaged 89.4 FPS at 1920 × 1080 and 111.7 FPS at 1280 × 720. Each measurement covered 7,000 frames of live first-person movement and combat with nine bots. The 95th-percentile frame times were 12.69 ms and 10.33 ms respectively. [Frame timings](Review/MatchPerformance.json)
