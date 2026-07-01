using System.Diagnostics;
using System.Net;
using System.Text.Json.Nodes;
using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Http;
using Microsoft.Extensions.Logging;

namespace CanvasApp;

internal static class CanvasServer
{
    private const string Host = "127.0.0.1";
    private const string ServerStateFile = ".server.json";

    internal static string CanvasUrl(int port, string canvasId) => $"http://{Host}:{port}/canvas/{CanvasRegistry.NormalizeCanvasId(canvasId)}/";

    internal static string ServerStatePath(CanvasRegistry registry) => Path.Combine(registry.Root, ServerStateFile);

    internal static JsonObject? ReadServerState(CanvasRegistry registry)
    {
        var path = ServerStatePath(registry);
        if (!File.Exists(path))
        {
            return null;
        }

        try
        {
            return JsonUtil.ReadObject(path);
        }
        catch
        {
            return null;
        }
    }

    internal static JsonObject WriteServerState(CanvasRegistry registry, int port, int? pid = null, bool running = true)
    {
        registry.EnsureRoot();
        var state = new JsonObject
        {
            ["kind"] = "canvas-server",
            ["host"] = Host,
            ["port"] = port,
            ["pid"] = pid ?? Environment.ProcessId,
            ["root"] = registry.Root,
            ["url"] = $"http://{Host}:{port}/",
            ["running"] = running,
            ["updated_at"] = CanvasRegistry.UtcNow(),
            ["canvases"] = ServerCanvasRecords(registry, port)
        };
        JsonUtil.WriteObject(ServerStatePath(registry), state);
        return state;
    }

    internal static void RefreshServerStateIfPresent(CanvasRegistry registry)
    {
        var state = ReadServerState(registry);
        if (state is null)
        {
            return;
        }

        var port = state["port"]?.GetValue<int>() ?? CanvasRegistry.DefaultServerPort;
        var pid = state["pid"]?.GetValue<int>();
        var running = state["running"]?.GetValue<bool>() ?? true;
        WriteServerState(registry, port, pid, running);
    }

    internal static JsonArray ServerCanvasRecords(CanvasRegistry registry, int port)
    {
        var records = new List<JsonObject>();
        foreach (var node in registry.ListCanvases())
        {
            if (node is not JsonObject metadata)
            {
                continue;
            }

            var id = metadata.StringValue("id");
            if (string.IsNullOrWhiteSpace(id))
            {
                continue;
            }

            var canvasDir = metadata.StringValue("storage_path") ?? "";
            var htmlPath = Path.Combine(canvasDir, "canvas.html");
            var modifiedAt = ModifiedAtSeconds([
                Path.Combine(canvasDir, "canvas.json"),
                Path.Combine(canvasDir, "state.json"),
                Path.Combine(canvasDir, "notes.md"),
                htmlPath
            ]);

            records.Add(new JsonObject
            {
                ["id"] = id,
                ["title"] = metadata.StringValue("title") ?? id,
                ["purpose"] = metadata.StringValue("purpose") ?? "",
                ["scope"] = metadata.StringValue("scope") ?? "",
                ["lifecycle"] = metadata.StringValue("lifecycle") ?? "",
                ["anchor"] = metadata.StringValue("anchor") ?? "",
                ["updated_at"] = metadata.StringValue("updated_at") ?? "",
                ["modified_at"] = modifiedAt,
                ["storage_path"] = canvasDir,
                ["has_html"] = File.Exists(htmlPath),
                ["url"] = CanvasUrl(port, id)
            });
        }

        var array = new JsonArray();
        foreach (var record in records.OrderBy(x => x.StringValue("title") ?? "", StringComparer.OrdinalIgnoreCase))
        {
            array.Add(record);
        }
        return array;
    }

    internal static async Task<bool> IsServerLiveAsync(CanvasRegistry registry)
    {
        var state = ReadServerState(registry);
        if (state is null)
        {
            return false;
        }

        var port = state["port"]?.GetValue<int>() ?? 0;
        if (port <= 0)
        {
            return false;
        }

        try
        {
            using var client = new HttpClient { Timeout = TimeSpan.FromSeconds(1.5) };
            using var response = await client.GetAsync($"http://{Host}:{port}/api/canvases");
            return response.StatusCode == HttpStatusCode.OK;
        }
        catch
        {
            return false;
        }
    }

    internal static async Task<JsonObject> StartServerProcessAsync(CanvasRegistry registry, string executable, int port)
    {
        var state = ReadServerState(registry);
        if (state is not null && await IsServerLiveAsync(registry))
        {
            return state;
        }

        var args = $"-root \"{registry.Root}\" serve -port {port} --foreground";
        var startInfo = OperatingSystem.IsWindows()
            ? new ProcessStartInfo
            {
                FileName = executable,
                Arguments = args,
                UseShellExecute = true,
                WindowStyle = ProcessWindowStyle.Hidden,
                WorkingDirectory = PathUtil.PluginRoot()
            }
            : new ProcessStartInfo
            {
                FileName = executable,
                Arguments = args,
                UseShellExecute = false,
                CreateNoWindow = true,
                WorkingDirectory = PathUtil.PluginRoot(),
                RedirectStandardInput = true,
                RedirectStandardOutput = true,
                RedirectStandardError = true
            };
        var process = Process.Start(startInfo);
        if (!OperatingSystem.IsWindows())
        {
            process?.StandardInput.Close();
        }
        return await WaitForServerAsync(registry);
    }

    internal static async Task<JsonObject> WaitForServerAsync(CanvasRegistry registry)
    {
        var deadline = DateTimeOffset.UtcNow.AddSeconds(8);
        JsonObject? lastState = null;
        while (DateTimeOffset.UtcNow < deadline)
        {
            lastState = ReadServerState(registry);
            if (lastState is not null
                && lastState["running"]?.GetValue<bool>() == true
                && await IsServerLiveAsync(registry))
            {
                return lastState;
            }

            await Task.Delay(150);
        }

        throw new CanvasException($"Canvas server did not start within 8.0s: {lastState?.ToJsonString(JsonUtil.Options)}");
    }

    internal static async Task<JsonObject> StopServerAsync(CanvasRegistry registry)
    {
        var state = ReadServerState(registry);
        if (state is null)
        {
            return new JsonObject { ["running"] = false, ["stopped"] = false, ["message"] = "No server state found." };
        }

        var port = state["port"]?.GetValue<int>() ?? 0;
        try
        {
            using var client = new HttpClient { Timeout = TimeSpan.FromSeconds(2) };
            await client.GetAsync($"http://{Host}:{port}/__shutdown");
        }
        catch
        {
            // Shutdown is best-effort; stale state is updated below.
        }

        var deadline = DateTimeOffset.UtcNow.AddSeconds(5);
        while (DateTimeOffset.UtcNow < deadline)
        {
            if (!await IsServerLiveAsync(registry))
            {
                break;
            }
            await Task.Delay(150);
        }

        state["running"] = false;
        state["stopped_at"] = CanvasRegistry.UtcNow();
        JsonUtil.WriteObject(ServerStatePath(registry), state);
        return new JsonObject
        {
            ["running"] = await IsServerLiveAsync(registry),
            ["stopped"] = true,
            ["state"] = state.DeepClone()
        };
    }

    internal static async Task RunForegroundServerAsync(CanvasRegistry registry, int port)
    {
        registry.EnsureRoot();
        var builder = WebApplication.CreateBuilder(new WebApplicationOptions
        {
            Args = [],
            ContentRootPath = PathUtil.PluginRoot()
        });
        builder.Logging.ClearProviders();
        builder.WebHost.UseUrls($"http://{Host}:{port}");
        var app = builder.Build();

        app.MapGet("/", async context =>
        {
            await ServeFileAsync(context, Path.Combine(PathUtil.PluginRoot(), "templates", "server-index.html"), "text/html; charset=utf-8");
        });
        app.MapGet("/server-state.json", () => Results.Json(WriteServerState(registry, ActualPort(app)), JsonUtil.Options));
        app.MapGet("/api/canvases", () =>
        {
            var state = WriteServerState(registry, ActualPort(app));
            return Results.Json(state["canvases"], JsonUtil.Options);
        });
        app.MapGet("/api/canvas/{id}/state", (string id) =>
        {
            var metadata = registry.GetCanvas(id);
            var statePath = Path.Combine(metadata.StringValue("storage_path")!, "state.json");
            var state = File.Exists(statePath) ? JsonUtil.ReadObject(statePath) : new JsonObject();
            return Results.Json(new JsonObject { ["metadata"] = metadata.DeepClone(), ["state"] = state.DeepClone() }, JsonUtil.Options);
        });
        app.MapGet("/__shutdown", (IHostApplicationLifetime lifetime) =>
        {
            _ = Task.Run(async () =>
            {
                await Task.Delay(50);
                lifetime.StopApplication();
            });
            return Results.Json(new JsonObject { ["ok"] = true, ["stopping"] = true }, JsonUtil.Options);
        });
        app.MapGet("/canvas/{id}/{**relative}", async (HttpContext context, string id, string? relative) =>
        {
            await ServeCanvasFileAsync(context, registry, id, relative);
        });
        app.MapGet("/canvas/{id}/", async (HttpContext context, string id) =>
        {
            await ServeCanvasFileAsync(context, registry, id, null);
        });

        await app.StartAsync();
        var actualPort = ActualPort(app);
        var state = WriteServerState(registry, actualPort);
        try
        {
            await app.WaitForShutdownAsync();
        }
        finally
        {
            state["running"] = false;
            state["stopped_at"] = CanvasRegistry.UtcNow();
            JsonUtil.WriteObject(ServerStatePath(registry), state);
        }
    }

    private static int ActualPort(WebApplication app)
    {
        var address = app.Urls.FirstOrDefault() ?? $"http://{Host}:{CanvasRegistry.DefaultServerPort}";
        return new Uri(address).Port;
    }

    private static async Task ServeCanvasFileAsync(HttpContext context, CanvasRegistry registry, string canvasId, string? relative)
    {
        var metadata = registry.GetCanvas(canvasId);
        var canvasDir = Path.GetFullPath(metadata.StringValue("storage_path")!);
        var relativePath = string.IsNullOrWhiteSpace(relative) ? "canvas.html" : relative.Replace('/', Path.DirectorySeparatorChar);
        var target = Path.GetFullPath(Path.Combine(canvasDir, relativePath));
        if (!string.Equals(canvasDir, target, StringComparison.OrdinalIgnoreCase) && !target.StartsWith(canvasDir + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase))
        {
            context.Response.StatusCode = StatusCodes.Status403Forbidden;
            await context.Response.WriteAsync("Path escapes canvas directory");
            return;
        }
        if (Directory.Exists(target))
        {
            target = Path.Combine(target, "canvas.html");
        }
        if (!File.Exists(target))
        {
            context.Response.StatusCode = StatusCodes.Status404NotFound;
            await context.Response.WriteAsync("Canvas file not found");
            return;
        }

        await ServeFileAsync(context, target, ContentType(target));
    }

    private static async Task ServeFileAsync(HttpContext context, string path, string contentType)
    {
        context.Response.Headers.CacheControl = "no-store";
        context.Response.ContentType = contentType;
        await context.Response.SendFileAsync(path);
    }

    private static string ContentType(string path)
    {
        var ext = Path.GetExtension(path).ToLowerInvariant();
        var type = ext switch
        {
            ".html" => "text/html",
            ".js" => "text/javascript",
            ".css" => "text/css",
            ".json" => "application/json",
            ".md" => "text/markdown",
            ".txt" => "text/plain",
            _ => "application/octet-stream"
        };
        return ext is ".html" or ".js" or ".css" or ".json" or ".md" or ".txt" ? $"{type}; charset=utf-8" : type;
    }

    private static double ModifiedAtSeconds(IEnumerable<string> paths)
    {
        var epoch = DateTimeOffset.UnixEpoch;
        var values = paths.Where(File.Exists).Select(path => (File.GetLastWriteTimeUtc(path) - epoch.UtcDateTime).TotalSeconds).ToList();
        return values.Count == 0 ? 0.0 : values.Max();
    }
}
