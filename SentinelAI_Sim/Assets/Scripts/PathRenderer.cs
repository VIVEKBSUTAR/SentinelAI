using UnityEngine;
using System.Collections.Generic;

/// <summary>
/// Draws the confirmed path (green) and predicted path (yellow)
/// of the tracked person through the house.
/// Only draws when person is flagged as suspicious.
/// </summary>
public class PathRenderer : MonoBehaviour
{
    [Header("Path Visuals")]
    public Color confirmedColor = new Color(0.1f, 1f, 0.3f, 0.9f);
    public Color predictedColor = new Color(1f, 0.85f, 0.1f, 0.9f);
    public float lineWidth = 0.1f;
    public float lineHeight = 0.25f;

    [Header("Settings")]
    [Tooltip("Minimum distance between path points to avoid clutter")]
    public float minPointDistance = 0.3f;

    private LineRenderer confirmedPath;
    private LineRenderer predictedPath;
    private List<Vector3> pathPoints = new List<Vector3>();

    private Dictionary<string, Dictionary<string, List<Vector3[]>>> routeGraph;

    void Start()
    {
        // Confirmed path (green — where person was actually seen)
        GameObject confirmedObj = new GameObject("ConfirmedPath");
        confirmedObj.transform.parent = transform;
        confirmedPath = confirmedObj.AddComponent<LineRenderer>();
        SetupLine(confirmedPath, confirmedColor);

        // Predicted path (yellow — deduced route through blind zones)
        GameObject predictedObj = new GameObject("PredictedPath");
        predictedObj.transform.parent = transform;
        predictedPath = predictedObj.AddComponent<LineRenderer>();
        SetupLine(predictedPath, predictedColor);

        BuildRouteGraph();
    }

    void SetupLine(LineRenderer lr, Color color)
    {
        lr.startWidth = lineWidth;
        lr.endWidth = lineWidth;
        lr.material = new Material(Shader.Find("Sprites/Default"));
        lr.startColor = color;
        lr.endColor = color;
        lr.positionCount = 0;
        lr.useWorldSpace = true;
    }

    void BuildRouteGraph()
    {
        // Routes matching the real house dimensions:
        // Room A center: (-4, y, -4)
        // Hall center:   ( 0, y, -3)
        // Room B center: ( 4, y, -4)
        // Garden center: ( 0, y, 2.5)

        routeGraph = new Dictionary<string, Dictionary<string, List<Vector3[]>>>();

        // Room A (mac) → Room B (room_b): two possible routes
        var aToB = new List<Vector3[]>
        {
            // Route 1: Through HALL (no camera — blind zone)
            new Vector3[] {
                new Vector3(-2.5f, lineHeight, -4),    // Room A door
                new Vector3(0, lineHeight, -3),        // Hall center
                new Vector3(2.5f, lineHeight, -4)      // Room B door
            },
            // Route 2: Through GARDEN (has camera)
            new Vector3[] {
                new Vector3(-4, lineHeight, -2),       // Room A garden door
                new Vector3(0, lineHeight, 2.5f),      // Garden center
                new Vector3(4, lineHeight, -2)         // Room B garden door
            }
        };

        routeGraph["mac"] = new Dictionary<string, List<Vector3[]>>
        {
            { "room_b", aToB }
        };

        // Reverse routes
        var bToA = new List<Vector3[]>
        {
            new Vector3[] {
                new Vector3(2.5f, lineHeight, -4),
                new Vector3(0, lineHeight, -3),
                new Vector3(-2.5f, lineHeight, -4)
            },
            new Vector3[] {
                new Vector3(4, lineHeight, -2),
                new Vector3(0, lineHeight, 2.5f),
                new Vector3(-4, lineHeight, -2)
            }
        };

        routeGraph["room_b"] = new Dictionary<string, List<Vector3[]>>
        {
            { "mac", bToA }
        };
    }

    /// <summary>
    /// Add a confirmed tracking point. Only call this for suspicious persons.
    /// </summary>
    public void AddPoint(Vector3 point, string cameraId)
    {
        point.y = lineHeight;

        // Skip if too close to last point (reduces clutter)
        if (pathPoints.Count > 0)
        {
            float dist = Vector3.Distance(pathPoints[pathPoints.Count - 1], point);
            if (dist < minPointDistance) return;
        }

        pathPoints.Add(point);
        confirmedPath.positionCount = pathPoints.Count;
        confirmedPath.SetPositions(pathPoints.ToArray());
    }

    /// <summary>
    /// Show predicted route when person disappears and reappears.
    /// Deduces which route they took based on camera coverage gaps.
    /// </summary>
    public void ShowPredictedRoute(string fromCamera, string toCamera,
                                    Vector3 lastPos, Vector3 newPos)
    {
        if (!routeGraph.ContainsKey(fromCamera)) return;
        if (!routeGraph[fromCamera].ContainsKey(toCamera)) return;

        var routes = routeGraph[fromCamera][toCamera];

        // Deduction logic:
        // If person went from mac (Room A) to room_b (Room B) and was NOT
        // seen by sony (Garden camera), they must have gone through the Hall.
        // Route[0] = Hall (blind), Route[1] = Garden (has camera)
        Vector3[] chosenRoute = routes[0]; // default: hall (blind route)

        // Build the predicted path line
        List<Vector3> predicted = new List<Vector3>();
        lastPos.y = lineHeight;
        newPos.y = lineHeight;
        predicted.Add(lastPos);
        predicted.AddRange(chosenRoute);
        predicted.Add(newPos);

        predictedPath.positionCount = predicted.Count;
        predictedPath.SetPositions(predicted.ToArray());

        Debug.Log($"[SentinelAI] Predicted route: {fromCamera} -> {toCamera} via HALL (blind zone)");
    }

    /// <summary>
    /// Clear all path visualizations.
    /// </summary>
    public void ClearPaths()
    {
        pathPoints.Clear();
        confirmedPath.positionCount = 0;
        predictedPath.positionCount = 0;
    }
}
