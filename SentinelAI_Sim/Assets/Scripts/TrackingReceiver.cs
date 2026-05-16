using UnityEngine;
using NativeWebSocket;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;
using System.Collections.Generic;

/// <summary>
/// Connects to SentinelAI's WebSocket and moves the avatar
/// based on real-time tracking data from the cameras.
/// Uses heavy smoothing to prevent jitter from small movements.
/// </summary>
public class TrackingReceiver : MonoBehaviour
{
    WebSocket websocket;

    [Header("Connection")]
    public string serverUrl = "ws://localhost:8000/ws/unity";

    [Header("References")]
    public Transform trackedPerson;
    public PathRenderer pathRenderer;

    [Header("Camera Zone Centers (World Pos)")]
    public Vector3 roomACenter = new Vector3(-4, 0.5f, -4);
    public Vector3 gardenCenter = new Vector3(0, 0.5f, 2.5f);
    public Vector3 roomBCenter = new Vector3(4, 0.5f, -4);

    [Header("Zone Dimensions")]
    public Vector2 roomSize = new Vector2(3f, 4f);     // 3m x 4m
    public Vector2 gardenSize = new Vector2(11f, 5f);   // 11m x 5m

    [Header("Smoothing")]
    [Tooltip("Higher = smoother but slower to respond")]
    public float smoothSpeed = 3f;
    [Tooltip("Minimum distance (meters) to register as actual movement")]
    public float moveThreshold = 0.15f;

    private Dictionary<string, Vector3> cameraPositions;
    private Dictionary<string, Vector2> cameraSizes;
    private string lastCameraId = "";
    private float lastSeenTime = 0;
    private Vector3 lastKnownPosition;
    private Vector3 targetPosition;
    private bool hasTarget = false;

    // Position buffer for extra smoothing
    private Queue<Vector3> posBuffer = new Queue<Vector3>();
    private const int BUFFER_SIZE = 5;

    // Thread-safe queue for incoming data
    private readonly Queue<TrackingData> dataQueue = new Queue<TrackingData>();

    async void Start()
    {
        cameraPositions = new Dictionary<string, Vector3>
        {
            { "mac", roomACenter },
            { "sony", gardenCenter },
            { "room_b", roomBCenter }
        };

        cameraSizes = new Dictionary<string, Vector2>
        {
            { "mac", roomSize },
            { "sony", gardenSize },
            { "room_b", roomSize }
        };

        if (trackedPerson != null)
            targetPosition = trackedPerson.position;

        websocket = new WebSocket(serverUrl);

        websocket.OnOpen += () => Debug.Log("[SentinelAI] Connected to tracking server");
        websocket.OnClose += (e) => Debug.Log("[SentinelAI] Disconnected");
        websocket.OnError += (e) => Debug.LogWarning("[SentinelAI] Error: " + e);

        websocket.OnMessage += (bytes) =>
        {
            string msg = System.Text.Encoding.UTF8.GetString(bytes);
            try
            {
                JObject wrapper = JObject.Parse(msg);
                string type = wrapper["type"]?.ToString();
                if (type == "tracking_update")
                {
                    TrackingData data = wrapper["data"].ToObject<TrackingData>();
                    lock (dataQueue) { dataQueue.Enqueue(data); }
                }
            }
            catch { }
        };

        await websocket.Connect();
    }

    void Update()
    {
#if !UNITY_WEBGL || UNITY_EDITOR
        websocket?.DispatchMessageQueue();
#endif

        // Process queued data on main thread
        lock (dataQueue)
        {
            while (dataQueue.Count > 0)
            {
                TrackingData data = dataQueue.Dequeue();
                ProcessTrackingData(data);
            }
        }

        // Smooth movement towards target
        if (hasTarget && trackedPerson != null)
        {
            trackedPerson.position = Vector3.Lerp(
                trackedPerson.position, targetPosition, Time.deltaTime * smoothSpeed
            );
        }
    }

    void ProcessTrackingData(TrackingData data)
    {
        if (!cameraPositions.ContainsKey(data.camera_id)) return;

        Vector3 zoneCenter = cameraPositions[data.camera_id];
        Vector2 zoneSize = cameraSizes.ContainsKey(data.camera_id)
            ? cameraSizes[data.camera_id]
            : new Vector2(3, 4);

        // Map normalized camera coords (0-1) to world position within zone
        Vector3 rawPos = new Vector3(
            zoneCenter.x + (data.x - 0.5f) * zoneSize.x,
            0.5f,
            zoneCenter.z + (data.y - 0.5f) * zoneSize.y
        );

        // Add to smoothing buffer
        posBuffer.Enqueue(rawPos);
        while (posBuffer.Count > BUFFER_SIZE)
            posBuffer.Dequeue();

        // Average the buffer for smooth position
        Vector3 smoothed = Vector3.zero;
        foreach (var p in posBuffer)
            smoothed += p;
        smoothed /= posBuffer.Count;

        // Only update target if movement exceeds threshold (filters jitter)
        float dist = Vector3.Distance(smoothed, targetPosition);
        if (dist > moveThreshold || !hasTarget)
        {
            targetPosition = smoothed;
            hasTarget = true;
        }

        // Detect camera zone transition
        if (lastCameraId != "" && lastCameraId != data.camera_id)
        {
            Debug.Log($"[SentinelAI] Person transitioned: {lastCameraId} -> {data.camera_id}");

            if (pathRenderer != null)
            {
                pathRenderer.ShowPredictedRoute(
                    lastCameraId, data.camera_id,
                    lastKnownPosition, smoothed
                );
            }

            // Clear buffer on camera switch to avoid lerping across rooms
            posBuffer.Clear();
            targetPosition = smoothed;
        }

        lastCameraId = data.camera_id;
        lastSeenTime = Time.time;
        lastKnownPosition = smoothed;

        // Only record path if person is suspicious
        if (pathRenderer != null &&
            (data.threat_level == "elevated" ||
             data.threat_level == "high" ||
             data.threat_level == "critical"))
        {
            pathRenderer.AddPoint(smoothed, data.camera_id);
        }
    }

    async void OnApplicationQuit()
    {
        if (websocket != null && websocket.State == WebSocketState.Open)
            await websocket.Close();
    }
}

[System.Serializable]
public class TrackingData
{
    public int person_id;
    public float x;
    public float y;
    public string camera_id;
    public string threat_level;
    public float timestamp;
}
