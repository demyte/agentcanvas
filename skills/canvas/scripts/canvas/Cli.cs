using System.Text.Json.Nodes;

namespace CanvasApp;

internal static class Cli
{
    private const string HelpText = """
Canvas CLI

Commands:
  init              Create a canvas.
  list              List active and/or archived canvases.
  get               Read canvas metadata.
  update-state      Merge state updates into state.json.
  validate          Validate a canvas folder.
  export-html       Export canvas.html and canvas-data.js.
  serve             Start the local Canvas HTTP server.
  open              Return a local HTTP URL for one canvas.
  server-status     Show local Canvas HTTP server status.
  server-stop       Stop the local Canvas HTTP server.
  associate-thread  Associate a Codex thread id with a canvas.
  promote           Record an explicit durable promotion reference.
  archive           Move an active canvas to archived lifecycle.

Common options:
  -root, --root PATH      Canvas root. Defaults to CANVAS_ROOT or ~/.agents/canvas.
  -h, --help, -?         Show help.

Examples:
  canvas init -id review-board -scope repo -anchor D:\Projects\repo -purpose "Track review work"
  canvas update-state -id review-board -set status=reviewing -set owner=codex
  canvas update-state -id review-board -merge-file .\state-update.json
  canvas validate -id review-board
  canvas export-html -id review-board
  canvas serve
  canvas open -id review-board
  canvas list -lifecycle active
""";

    internal static async Task<int> RunAsync(string[] args)
    {
        try
        {
            if (args.Length == 0 || IsHelp(args[0]))
            {
                Console.WriteLine(HelpText);
                return 0;
            }

            var tokens = new Queue<string>(args);
            var root = ReadOptionalRoot(tokens);
            if (tokens.Count == 0)
            {
                Console.WriteLine(HelpText);
                return 0;
            }

            var command = tokens.Dequeue();
            if (tokens.Any(IsHelp))
            {
                Console.WriteLine(CommandHelp(command));
                return 0;
            }

            var registry = new CanvasRegistry(root);
            switch (command)
            {
                case "init":
                    return await RunInitAsync(registry, tokens);
                case "list":
                {
                    var options = ReadOptions(tokens);
                    JsonUtil.WriteStdout(registry.ListCanvases(Value(options, "lifecycle", fallback: null), Value(options, "thread-id", fallback: null)));
                    return 0;
                }
                case "get":
                {
                    var options = ReadOptions(tokens);
                    JsonUtil.WriteStdout(registry.GetCanvas(RequiredValue(options, "id"), Value(options, "lifecycle", fallback: null)));
                    return 0;
                }
                case "validate":
                {
                    var options = ReadOptions(tokens);
                    var result = registry.ValidateCanvas(RequiredValue(options, "id"), Value(options, "lifecycle", fallback: null));
                    CanvasServer.RefreshServerStateIfPresent(registry);
                    JsonUtil.WriteStdout(result);
                    return result["valid"]!.GetValue<bool>() ? 0 : 2;
                }
                case "archive":
                    JsonUtil.WriteStdout(registry.ArchiveCanvas(RequiredId(tokens)));
                    CanvasServer.RefreshServerStateIfPresent(registry);
                    return 0;
                case "associate-thread":
                    return await RunAssociateThreadAsync(registry, tokens);
                case "promote":
                    return await RunPromoteAsync(registry, tokens);
                case "export-html":
                    return await RunExportHtmlAsync(registry, tokens);
                case "update-state":
                    return await RunUpdateStateAsync(registry, tokens);
                case "serve":
                    return await RunServeAsync(registry, tokens);
                case "server-status":
                    return await RunServerStatusAsync(registry);
                case "server-stop":
                    JsonUtil.WriteStdout(await CanvasServer.StopServerAsync(registry));
                    return 0;
                case "open":
                    return await RunOpenAsync(registry, tokens);
                default:
                    throw new CanvasException($"Unknown command: {command}");
            }
        }
        catch (CanvasException exc)
        {
            JsonUtil.WriteStdout(new
            {
                error = new
                {
                    type = exc.GetType().Name,
                    message = exc.Message,
                    recoverable = true
                }
            });
            return 1;
        }
    }

    private static async Task<int> RunInitAsync(CanvasRegistry registry, Queue<string> tokens)
    {
        var options = ReadOptions(tokens, repeatable: ["-human-action", "--human-action", "-agent-action", "--agent-action", "-promotion-target", "--promotion-target", "-associated-thread", "--associated-thread"]);
        var result = registry.InitCanvas(
            RequiredValue(options, "id"),
            RequiredValue(options, "scope"),
            Value(options, "anchor"),
            Value(options, "title"),
            Value(options, "purpose"),
            Values(options, "human-action"),
            Values(options, "agent-action"),
            Values(options, "promotion-target"),
            Values(options, "associated-thread"));
        CanvasServer.RefreshServerStateIfPresent(registry);
        JsonUtil.WriteStdout(result);
        await Task.CompletedTask;
        return 0;
    }

    private static async Task<int> RunAssociateThreadAsync(CanvasRegistry registry, Queue<string> tokens)
    {
        var options = ReadOptions(tokens);
        var id = RequiredValue(options, "id");
        var threadId = Value(options, "thread-id");
        if (string.IsNullOrWhiteSpace(threadId))
        {
            throw new CanvasException("Thread id is required. Use -thread-id <thread-id>.");
        }
        var result = registry.AssociateThread(id, threadId, Value(options, "lifecycle", "active"));
        CanvasServer.RefreshServerStateIfPresent(registry);
        JsonUtil.WriteStdout(result);
        await Task.CompletedTask;
        return 0;
    }

    private static async Task<int> RunPromoteAsync(CanvasRegistry registry, Queue<string> tokens)
    {
        var options = ReadOptions(tokens);
        var result = registry.PromoteCanvas(RequiredValue(options, "id"), RequiredValue(options, "target"), RequiredValue(options, "reference"), Value(options, "note"));
        CanvasServer.RefreshServerStateIfPresent(registry);
        JsonUtil.WriteStdout(result);
        await Task.CompletedTask;
        return 0;
    }

    private static async Task<int> RunExportHtmlAsync(CanvasRegistry registry, Queue<string> tokens)
    {
        var options = ReadOptions(tokens);
        var result = registry.ExportHtml(RequiredValue(options, "id"), Value(options, "lifecycle"), Value(options, "output"));
        CanvasServer.RefreshServerStateIfPresent(registry);
        JsonUtil.WriteStdout(result);
        await Task.CompletedTask;
        return 0;
    }

    private static async Task<int> RunUpdateStateAsync(CanvasRegistry registry, Queue<string> tokens)
    {
        var options = ReadOptions(tokens, repeatable: ["-set", "--set", "-merge-file", "--merge-file"]);
        var updates = StateUpdates(options);
        var result = registry.UpdateState(RequiredValue(options, "id"), updates);
        CanvasServer.RefreshServerStateIfPresent(registry);
        JsonUtil.WriteStdout(result);
        await Task.CompletedTask;
        return 0;
    }

    private static async Task<int> RunServeAsync(CanvasRegistry registry, Queue<string> tokens)
    {
        var options = ReadOptions(tokens, flags: ["--foreground"]);
        var port = int.TryParse(Value(options, "port"), out var parsed) ? parsed : CanvasRegistry.DefaultServerPort;
        if (options.ContainsKey("foreground"))
        {
            var liveState = await CanvasServer.ReadLiveServerStateAtPortAsync(port);
            if (liveState is not null)
            {
                JsonUtil.WriteStdout(CanvasServer.AlreadyRunningResponse(liveState));
                return 0;
            }

            await CanvasServer.RunForegroundServerAsync(registry, port);
            return 0;
        }

        var executable = Environment.ProcessPath ?? throw new CanvasException("Unable to resolve current executable path.");
        JsonUtil.WriteStdout(await CanvasServer.StartServerProcessAsync(registry, executable, port));
        return 0;
    }

    private static async Task<int> RunServerStatusAsync(CanvasRegistry registry)
    {
        var state = CanvasServer.ReadServerState(registry);
        var live = await CanvasServer.IsServerLiveAsync(registry);
        if (live && state is not null)
        {
            var port = state["port"]?.GetValue<int>() ?? CanvasRegistry.DefaultServerPort;
            var pid = state["pid"]?.GetValue<int>();
            state = CanvasServer.WriteServerState(registry, port, pid);
        }
        JsonUtil.WriteStdout(new JsonObject { ["running"] = live, ["state"] = state?.DeepClone() });
        return 0;
    }

    private static async Task<int> RunOpenAsync(CanvasRegistry registry, Queue<string> tokens)
    {
        var options = ReadOptions(tokens);
        var metadata = registry.GetCanvas(RequiredValue(options, "id"));
        var state = CanvasServer.ReadServerState(registry);
        if (state is null || !await CanvasServer.IsServerLiveAsync(registry))
        {
            var executable = Environment.ProcessPath ?? throw new CanvasException("Unable to resolve current executable path.");
            var port = int.TryParse(Value(options, "port"), out var parsed) ? parsed : CanvasRegistry.DefaultServerPort;
            state = await CanvasServer.StartServerProcessAsync(registry, executable, port);
        }
        var activePort = state["port"]?.GetValue<int>() ?? CanvasRegistry.DefaultServerPort;
        JsonUtil.WriteStdout(new JsonObject
        {
            ["id"] = metadata.StringValue("id"),
            ["url"] = CanvasServer.CanvasUrl(activePort, metadata.StringValue("id")!),
            ["index_url"] = state.StringValue("url"),
            ["server"] = state.DeepClone()
        });
        return 0;
    }

    private static string? ReadOptionalRoot(Queue<string> tokens)
    {
        if (tokens.Count >= 2 && (tokens.Peek() == "-root" || tokens.Peek() == "--root"))
        {
            tokens.Dequeue();
            return tokens.Dequeue();
        }
        return null;
    }

    private static string? ReadOption(Queue<string> tokens, params string[] names)
    {
        var options = ReadOptions(tokens);
        foreach (var name in names.Select(NormalizeName))
        {
            if (options.TryGetValue(name, out var values) && values.Count > 0)
            {
                return values[^1];
            }
        }
        return null;
    }

    private static string RequiredId(Queue<string> tokens)
    {
        var options = ReadOptions(tokens);
        return RequiredValue(options, "id");
    }

    private static Dictionary<string, List<string>> ReadOptions(Queue<string> tokens, string[]? repeatable = null, string[]? flags = null)
    {
        var result = new Dictionary<string, List<string>>(StringComparer.OrdinalIgnoreCase);
        var flagSet = (flags ?? []).Select(NormalizeName).ToHashSet(StringComparer.OrdinalIgnoreCase);
        string? positional = null;
        while (tokens.Count > 0)
        {
            var token = tokens.Dequeue();
            if (!token.StartsWith("-", StringComparison.Ordinal))
            {
                positional ??= token;
                continue;
            }
            var name = NormalizeName(token);
            if (flagSet.Contains(name))
            {
                result[name] = [];
                continue;
            }
            if (tokens.Count == 0)
            {
                throw new CanvasException($"{token} requires a value.");
            }
            AddOption(result, name, tokens.Dequeue());
        }
        if (positional is not null && !result.ContainsKey("id"))
        {
            result["id"] = [positional];
        }
        return result;
    }

    private static JsonObject StateUpdates(Dictionary<string, List<string>> options)
    {
        var updates = new JsonObject();
        foreach (var path in Values(options, "merge-file") ?? [])
        {
            var payload = JsonUtil.ReadObject(PathUtil.ExpandPath(path));
            foreach (var kv in payload)
            {
                updates[kv.Key] = kv.Value?.DeepClone();
            }
        }
        foreach (var raw in Values(options, "set") ?? [])
        {
            var index = raw.IndexOf('=');
            if (index < 0)
            {
                throw new CanvasException("--set values must use KEY=VALUE");
            }
            SetNested(updates, raw[..index].Trim(), raw[(index + 1)..]);
        }
        if (updates.Count == 0)
        {
            throw new CanvasException("No state updates supplied. Use -set KEY=VALUE or -merge-file PATH.");
        }
        return updates;
    }

    private static void SetNested(JsonObject data, string dottedKey, string value)
    {
        var parts = dottedKey.Split('.', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries);
        if (parts.Length == 0)
        {
            throw new CanvasException("--set keys must not be empty");
        }
        var target = data;
        foreach (var part in parts[..^1])
        {
            if (target[part] is not JsonObject child)
            {
                child = new JsonObject();
                target[part] = child;
            }
            target = child;
        }
        target[parts[^1]] = value;
    }

    private static void AddOption(Dictionary<string, List<string>> options, string name, string value)
    {
        if (!options.TryGetValue(name, out var values))
        {
            values = [];
            options[name] = values;
        }
        values.Add(value);
    }

    private static string RequiredValue(Dictionary<string, List<string>> options, string name)
    {
        var value = Value(options, name);
        if (string.IsNullOrWhiteSpace(value))
        {
            if (name == "id")
            {
                throw new CanvasException("Canvas id is required. Use -id <canvas-id>.");
            }
            throw new CanvasException($"{name} is required.");
        }
        return value;
    }

    private static string? Value(Dictionary<string, List<string>> options, string name, string? fallback = "")
    {
        return options.TryGetValue(name, out var values) && values.Count > 0 ? values[^1] : fallback;
    }

    private static List<string>? Values(Dictionary<string, List<string>> options, string name)
    {
        return options.TryGetValue(name, out var values) ? values : null;
    }

    private static string NormalizeName(string raw) => raw.TrimStart('-');
    private static bool IsHelp(string value) => value is "-h" or "--help" or "-?";

    private static string CommandHelp(string command)
    {
        return command switch
        {
            "init" => "usage: canvas init [-h] [-?] [-root ROOT] [-id ID] -scope {repo,project,thread,user} [-anchor ANCHOR] [-title TITLE] [-purpose PURPOSE] [-human-action HUMAN_ACTIONS] [-agent-action AGENT_ACTIONS] [-promotion-target PROMOTION_TARGETS] [-associated-thread ASSOCIATED_THREADS]\n\noptions:\n  -id, --id ID\n  -scope, --scope {repo,project,thread,user}\n",
            _ => HelpText
        };
    }
}
