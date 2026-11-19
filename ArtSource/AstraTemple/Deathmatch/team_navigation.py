"""Place deployment area modifiers at the actual PlayerStarts and inspect their baked paths."""
import math
import unreal as u


def world():
    current = u.get_editor_subsystem(u.UnrealEditorSubsystem).get_editor_world()
    if current.get_name() != "L_CanopyDeathmatch":
        raise RuntimeError("Open the Canopy Deathmatch level before editing its deployment navigation.")
    return current


def starts_and_centers():
    actors = u.get_editor_subsystem(u.EditorActorSubsystem)
    starts = {"Red": [], "Blue": []}
    for actor in actors.get_all_level_actors():
        if isinstance(actor, u.PlayerStart) and str(actor.player_start_tag) in starts:
            starts[str(actor.player_start_tag)].append(actor.get_actor_location())
    if any(len(locations) != 6 for locations in starts.values()):
        raise ValueError("Expected six player starts for each team.")
    centers = {side: u.Vector(*(sum(getattr(p, axis) for p in locations) / len(locations) for axis in "xyz"))
               for side, locations in starts.items()}
    return starts, centers


def install():
    current = world()
    actors = u.get_editor_subsystem(u.EditorActorSubsystem)
    _, centers = starts_and_centers()
    by_label = {actor.get_actor_label(): actor for actor in actors.get_all_level_actors()
                if isinstance(actor, u.TempleDeploymentNavigation)}
    for side, center in centers.items():
        label = f"{side} Deployment Navigation"
        marker = by_label.get(label)
        if marker is None:
            marker = actors.spawn_actor_from_class(u.TempleDeploymentNavigation, center)
        marker.modify()
        marker.set_actor_label(label)
        marker.set_folder_path("Deathmatch/Navigation")
        marker.set_actor_location(center, False, True)
        area = getattr(u, f"Temple{side}DeploymentArea")
        marker.set_area_class(area)
        marker.set_area_class_to_replace(u.NavArea_Default)
    install_west_spring_exclusion(actors)
    u.SystemLibrary.execute_console_command(current, "RebuildNavigation")
    return {side: [getattr(center, axis) / 100 for axis in "xyz"] for side, center in centers.items()}


def install_west_spring_exclusion(actors):
    """Keep path following off the narrow 48-degree rock face beside the cloister trail."""
    label = "West Spring Escarpment Navigation"
    marker = next((actor for actor in actors.get_all_level_actors() if actor.get_actor_label() == label), None)
    location = u.Vector(1490, -4776, 620)
    rotation = u.Rotator(0, 0, -33)
    if marker is None:
        marker = actors.spawn_actor_from_class(u.NavModifierVolume, location, rotation)
    marker.modify()
    marker.set_actor_label(label)
    marker.set_folder_path("Deathmatch/Navigation")
    marker.set_actor_location_and_rotation(location, rotation, False, True)
    marker.set_actor_scale3d(u.Vector(1.54, .46, 1.5))
    marker.set_editor_property("area_class", u.NavArea_Null)
    return marker


def ready():
    return not u.NavigationSystemV1.is_navigation_being_built_or_locked(world())


def save():
    if not ready():
        raise RuntimeError("Navigation is still building.")
    if not u.get_editor_subsystem(u.LevelEditorSubsystem).save_current_level():
        raise RuntimeError("The deployment navigation was not saved.")


def inspect():
    current = world()
    _, centers = starts_and_centers()
    routes = {"East Quay": (-7, 21.7, 4), "Ford Landing": (11, 39, 4.4), "West Plaza": (12, -23, 4)}
    goal = u.Vector(3100, 0, 1200)
    nav = u.NavigationSystemV1
    def nearest(point):
        result = nav.project_point_to_navigation(current, point, None, None, u.Vector(190, 190, 450))
        if result is None:
            raise ValueError(f"No walkable point near {point}")
        return result
    result = {}
    for role, filter_class in (("Default", None), ("Red", u.TempleRedRouteFilter), ("Blue", u.TempleBlueRouteFilter)):
        for label, start in routes.items():
            origin = nearest(u.Vector(*(x * 100 for x in start)))
            path = nav.find_path_to_location_synchronously(current, origin, nearest(goal), None, filter_class)
            points = path.path_points if path else []
            clearance = 1.e6
            inside = 0.
            center = centers["Blue"]
            for a, b in zip(points, points[1:]):
                dx, dy, dz = b.x - a.x, b.y - a.y, b.z - a.z
                length = math.hypot(dx, dy)
                count = max(1, math.ceil(length / 2))
                for i in range(count):
                    t = (i + .5) / count
                    if abs(a.z + t * dz + 96 - center.z) < 430:
                        distance = math.hypot(a.x + t * dx - center.x, a.y + t * dy - center.y) - 650
                        clearance = min(clearance, distance)
                        if distance < 0:
                            inside += length / count
            result[f"{label}/{role}"] = {
                "full": bool(path and path.is_valid() and not path.is_partial()),
                "min_blue_clearance_m": round(clearance / 100, 3), "inside_blue_m": round(inside / 100, 3),
                "path_m": [[round(getattr(p, axis) / 100, 2) for axis in "xyz"] for p in points],
            }
    return result
