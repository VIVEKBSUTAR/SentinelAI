using UnityEngine;
using UnityEditor;

/// <summary>
/// Editor tool that auto-generates the SentinelAI demo house layout.
/// Room A = 3m x 4m, Hall = 5m x 6m, Garden proportionally sized.
/// Use: Top menu → SentinelAI → Build House Layout
/// </summary>
public class HouseBuilder : EditorWindow
{
    // Real dimensions (1 Unity unit = 1 meter)
    // Room A: 3m wide x 4m deep
    // Room B: 3m wide x 4m deep
    // Hall:   5m wide x 6m deep (connecting rooms)
    // Garden: 11m wide x 5m deep (below rooms)

    [MenuItem("SentinelAI/Build House Layout")]
    static void BuildHouse()
    {
        if (!EditorUtility.DisplayDialog(
            "Build House Layout",
            "This will rebuild the house layout with correct dimensions.\n\n" +
            "Room A: 3m x 4m\nHall: 5m x 6m\nRoom B: 3m x 4m\nGarden: 11m x 5m\n\nContinue?",
            "Build", "Cancel"))
            return;

        // Clean up existing
        GameObject existing = GameObject.Find("House");
        if (existing != null) DestroyImmediate(existing);
        // Also remove old avatar
        GameObject oldAvatar = GameObject.Find("TrackedPerson");
        if (oldAvatar != null) DestroyImmediate(oldAvatar);

        GameObject house = new GameObject("House");

        // Materials
        Material floorMat = CreateMat("FloorMat", new Color(0.2f, 0.2f, 0.25f));
        Material wallMat = CreateMat("WallMat", new Color(0.35f, 0.38f, 0.42f));
        Material gardenFloorMat = CreateMat("GardenFloorMat", new Color(0.15f, 0.35f, 0.15f));
        Material camMat = CreateMat("CameraMat", new Color(0f, 0.9f, 1f));
        Material doorMat = CreateMat("DoorMat", new Color(0.5f, 0.35f, 0.2f));

        float wallH = 2.8f;      // wall height
        float wallT = 0.15f;     // wall thickness
        float doorW = 0.9f;      // door opening width

        // ── Layout coordinates ──────────────────────────────
        // Room A:  X from -5.5 to -2.5  (3m), Z from -6 to -2 (4m)
        // Hall:    X from -2.5 to  2.5  (5m), Z from -6 to  0 (6m)
        // Room B:  X from  2.5 to  5.5  (3m), Z from -6 to -2 (4m)
        // Garden:  X from -5.5 to  5.5 (11m), Z from  0 to  5 (5m)

        // ===================== FLOORS =====================
        // Room A floor
        CreateBox("FloorRoomA", house.transform, new Vector3(-4, 0, -4),
                  new Vector3(3, 0.1f, 4), floorMat);
        // Hall floor
        CreateBox("FloorHall", house.transform, new Vector3(0, 0, -3),
                  new Vector3(5, 0.1f, 6), floorMat);
        // Room B floor
        CreateBox("FloorRoomB", house.transform, new Vector3(4, 0, -4),
                  new Vector3(3, 0.1f, 4), floorMat);
        // Garden floor
        CreateBox("FloorGarden", house.transform, new Vector3(0, 0, 2.5f),
                  new Vector3(11, 0.1f, 5), gardenFloorMat);

        // ===================== ROOM A WALLS =====================
        GameObject roomA = new GameObject("RoomA_Walls");
        roomA.transform.parent = house.transform;

        float hy = wallH / 2f;

        // Left wall (full)
        CreateBox("Left", roomA.transform, new Vector3(-5.5f, hy, -4),
                  new Vector3(wallT, wallH, 4), wallMat);
        // Back wall (full)
        CreateBox("Back", roomA.transform, new Vector3(-4, hy, -6),
                  new Vector3(3, wallH, wallT), wallMat);
        // Front wall - left piece
        CreateBox("FrontL", roomA.transform, new Vector3(-5.05f, hy, -2),
                  new Vector3(0.9f, wallH, wallT), wallMat);
        // Front wall - right piece (door gap to garden in between)
        CreateBox("FrontR", roomA.transform, new Vector3(-3.05f, hy, -2),
                  new Vector3(1.9f, wallH, wallT), wallMat);
        // Right wall - top piece (door gap to hall)
        CreateBox("RightTop", roomA.transform, new Vector3(-2.5f, hy, -5.55f),
                  new Vector3(wallT, wallH, 0.9f), wallMat);
        // Right wall - bottom piece
        CreateBox("RightBot", roomA.transform, new Vector3(-2.5f, hy, -2.45f),
                  new Vector3(wallT, wallH, 0.9f), wallMat);

        // ===================== ROOM B WALLS =====================
        GameObject roomB = new GameObject("RoomB_Walls");
        roomB.transform.parent = house.transform;

        // Right wall (full)
        CreateBox("Right", roomB.transform, new Vector3(5.5f, hy, -4),
                  new Vector3(wallT, wallH, 4), wallMat);
        // Back wall (full)
        CreateBox("Back", roomB.transform, new Vector3(4, hy, -6),
                  new Vector3(3, wallH, wallT), wallMat);
        // Front wall - right piece
        CreateBox("FrontR", roomB.transform, new Vector3(5.05f, hy, -2),
                  new Vector3(0.9f, wallH, wallT), wallMat);
        // Front wall - left piece (door gap to garden)
        CreateBox("FrontL", roomB.transform, new Vector3(3.05f, hy, -2),
                  new Vector3(1.9f, wallH, wallT), wallMat);
        // Left wall - top piece (door to hall)
        CreateBox("LeftTop", roomB.transform, new Vector3(2.5f, hy, -5.55f),
                  new Vector3(wallT, wallH, 0.9f), wallMat);
        // Left wall - bottom piece
        CreateBox("LeftBot", roomB.transform, new Vector3(2.5f, hy, -2.45f),
                  new Vector3(wallT, wallH, 0.9f), wallMat);

        // ===================== HALL WALLS =====================
        GameObject hall = new GameObject("Hall_Walls");
        hall.transform.parent = house.transform;

        // Back wall (between the two rooms)
        CreateBox("Back", hall.transform, new Vector3(0, hy, -6),
                  new Vector3(5, wallH, wallT), wallMat);
        // Front wall - left piece (door gap to garden)
        CreateBox("FrontL", hall.transform, new Vector3(-1.7f, hy, 0),
                  new Vector3(1.6f, wallH, wallT), wallMat);
        // Front wall - right piece
        CreateBox("FrontR", hall.transform, new Vector3(1.7f, hy, 0),
                  new Vector3(1.6f, wallH, wallT), wallMat);

        // ===================== GARDEN OUTER WALLS =====================
        GameObject garden = new GameObject("Garden_Walls");
        garden.transform.parent = house.transform;

        // Left outer wall
        CreateBox("Left", garden.transform, new Vector3(-5.5f, hy, 2.5f),
                  new Vector3(wallT, wallH, 5), wallMat);
        // Right outer wall
        CreateBox("Right", garden.transform, new Vector3(5.5f, hy, 2.5f),
                  new Vector3(wallT, wallH, 5), wallMat);
        // Front outer wall
        CreateBox("Front", garden.transform, new Vector3(0, hy, 5),
                  new Vector3(11, wallH, wallT), wallMat);

        // ===================== CAMERA INDICATORS =====================
        CreateBox("Cam_RoomA", house.transform, new Vector3(-5.2f, 2.5f, -5.7f),
                  new Vector3(0.3f, 0.3f, 0.3f), camMat);
        CreateBox("Cam_Garden", house.transform, new Vector3(0, 2.5f, 4.7f),
                  new Vector3(0.3f, 0.3f, 0.3f), camMat);
        CreateBox("Cam_RoomB", house.transform, new Vector3(5.2f, 2.5f, -5.7f),
                  new Vector3(0.3f, 0.3f, 0.3f), camMat);

        // ===================== ROOM LABELS =====================
        CreateLabel("Lbl_RoomA", house.transform, new Vector3(-4, 0.15f, -4), "ROOM A\n3m x 4m\n(Camera 1)");
        CreateLabel("Lbl_Hall", house.transform, new Vector3(0, 0.15f, -3), "HALL\n5m x 6m\n(No Camera)");
        CreateLabel("Lbl_RoomB", house.transform, new Vector3(4, 0.15f, -4), "ROOM B\n3m x 4m\n(Camera 3)");
        CreateLabel("Lbl_Garden", house.transform, new Vector3(0, 0.15f, 2.5f), "GARDEN\n11m x 5m\n(Camera 2)");

        // ===================== TOP-DOWN CAMERA =====================
        GameObject camObj = GameObject.Find("Main Camera");
        if (camObj != null)
        {
            camObj.transform.position = new Vector3(0, 18, -0.5f);
            camObj.transform.rotation = Quaternion.Euler(90, 0, 0);
            Camera cam = camObj.GetComponent<Camera>();
            cam.orthographic = true;
            cam.orthographicSize = 8;
            cam.backgroundColor = new Color(0.05f, 0.07f, 0.1f);
        }

        // ===================== TRACKED PERSON =====================
        GameObject avatar = GameObject.CreatePrimitive(PrimitiveType.Capsule);
        avatar.name = "TrackedPerson";
        avatar.transform.position = new Vector3(-4, 0.5f, -4);
        avatar.transform.localScale = new Vector3(0.4f, 0.4f, 0.4f);
        Material avatarMat = CreateMat("AvatarMat", new Color(1f, 0.2f, 0.2f));
        avatarMat.SetFloat("_Glossiness", 0.8f);
        avatar.GetComponent<Renderer>().material = avatarMat;

        Selection.activeGameObject = house;
        EditorUtility.DisplayDialog("Done!",
            "House rebuilt with correct dimensions!\n\n" +
            "Room A: 3m x 4m (left)\n" +
            "Hall: 5m x 6m (center, no camera)\n" +
            "Room B: 3m x 4m (right)\n" +
            "Garden: 11m x 5m (bottom)\n\n" +
            "IMPORTANT: Re-drag TrackedPerson into\n" +
            "GameController's Tracked Person field!", "OK");
    }

    static GameObject CreateBox(string name, Transform parent, Vector3 pos, Vector3 scale, Material mat)
    {
        GameObject obj = GameObject.CreatePrimitive(PrimitiveType.Cube);
        obj.name = name;
        obj.transform.parent = parent;
        obj.transform.position = pos;
        obj.transform.localScale = scale;
        obj.GetComponent<Renderer>().material = mat;
        return obj;
    }

    static void CreateLabel(string name, Transform parent, Vector3 pos, string text)
    {
        GameObject obj = new GameObject(name);
        obj.transform.parent = parent;
        obj.transform.position = pos;
        obj.transform.rotation = Quaternion.Euler(90, 0, 0);
        TextMesh tm = obj.AddComponent<TextMesh>();
        tm.text = text;
        tm.fontSize = 32;
        tm.characterSize = 0.1f;
        tm.alignment = TextAlignment.Center;
        tm.anchor = TextAnchor.MiddleCenter;
        tm.color = new Color(1, 1, 1, 0.4f);
    }

    static Material CreateMat(string name, Color color)
    {
        Material mat = new Material(Shader.Find("Standard"));
        mat.name = name;
        mat.color = color;
        return mat;
    }
}
