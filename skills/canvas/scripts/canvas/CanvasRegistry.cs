using System.Text.Json;
using System.Text.Json.Nodes;
using System.Text.RegularExpressions;

namespace CanvasApp;

internal sealed class CanvasRegistry
{
    internal const int DefaultServerPort = 12345;
    private static readonly string[] Scopes = ["repo", "project", "thread", "user"];
    private static readonly string[] Lifecycles = ["active", "archived"];
    private static readonly string[] DefaultHumanActions = ["inspect", "edit_notes", "mark_done", "request_refresh", "request_promotion"];
    private static readonly string[] DefaultAgentActions = ["refresh_state", "add_item", "update_item", "summarize_changes", "regenerate_surface", "validate_surface", "archive_canvas"];
    private static readonly string[] DefaultPromotionTargets = ["repo-doc", "project-memory", "project-dashboard", "static-site-catalog", "issue-comment", "pull-request-comment", "final-report"];

    internal CanvasRegistry(string? root = null)
    {
        Root = PathUtil.FullPath(root ?? Environment.GetEnvironmentVariable("CANVAS_ROOT") ?? Path.Combine("~", ".agents", "canvas"));
        Active = Path.Combine(Root, "active");
        Archived = Path.Combine(Root, "archived");
    }

    internal string Root { get; }
    internal string Active { get; }
    internal string Archived { get; }

    internal void EnsureRoot()
    {
        Directory.CreateDirectory(Active);
        Directory.CreateDirectory(Archived);
    }

    internal JsonObject InitCanvas(
        string canvasId,
        string scope,
        string anchor = "",
        string title = "",
        string purpose = "",
        List<string>? humanActions = null,
        List<string>? agentActions = null,
        List<string>? promotionTargets = null,
        List<string>? associatedThreads = null)
    {
        EnsureRoot();
        var id = NormalizeCanvasId(canvasId);
        if (!Scopes.Contains(scope))
        {
            throw new CanvasValidationError("Scope must be one of ['project', 'repo', 'thread', 'user'].");
        }

        var canvasDir = Path.Combine(Active, id);
        var archivedDir = Path.Combine(Archived, id);
        if (Directory.Exists(canvasDir) || Directory.Exists(archivedDir))
        {
            throw new CanvasValidationError($"Canvas already exists: {id}");
        }

        var now = UtcNow();
        Directory.CreateDirectory(canvasDir);
        try
        {
            var stateFiles = new[] { "state.json", "notes.md" };
            var metadata = new JsonObject
            {
                ["id"] = id,
                ["kind"] = "canvas",
                ["lifecycle"] = "active",
                ["authority"] = "working-artifact",
                ["scope"] = scope,
                ["anchor"] = anchor,
                ["anchor_fingerprint"] = AnchorFingerprint(anchor),
                ["storage_policy"] = "external-user-codex",
                ["storage_path"] = canvasDir,
                ["title"] = string.IsNullOrWhiteSpace(title) ? id : title,
                ["purpose"] = purpose,
                ["created_from_thread"] = "",
                ["last_updated_from_thread"] = "",
                ["associatedThreads"] = JsonUtil.StringArray(CleanList(associatedThreads, [])),
                ["created_at"] = now,
                ["updated_at"] = now,
                ["state_files"] = JsonUtil.StringArray(stateFiles),
                ["human_actions"] = JsonUtil.StringArray(CleanList(humanActions, DefaultHumanActions)),
                ["agent_actions"] = JsonUtil.StringArray(CleanList(agentActions, DefaultAgentActions)),
                ["shared_state"] = JsonUtil.StringArray(stateFiles),
                ["promotion_targets"] = JsonUtil.StringArray(CleanList(promotionTargets, DefaultPromotionTargets)),
                ["promotions"] = new JsonArray()
            };

            JsonUtil.WriteObject(Path.Combine(canvasDir, "canvas.json"), metadata);
            JsonUtil.WriteObject(
                Path.Combine(canvasDir, "state.json"),
                new JsonObject
                {
                    ["items"] = new JsonArray(),
                    ["decisions"] = new JsonArray(),
                    ["open_questions"] = new JsonArray(),
                    ["updated_at"] = now
                });
            File.WriteAllText(Path.Combine(canvasDir, "notes.md"), $"# {metadata["title"]!.GetValue<string>()}\n\nPurpose: {(string.IsNullOrWhiteSpace(purpose) ? "Working canvas." : purpose)}\n");
            File.WriteAllText(Path.Combine(canvasDir, "README.md"), ReadmeText(metadata));
            return metadata;
        }
        catch (Exception)
        {
            if (Directory.Exists(canvasDir))
            {
                Directory.Delete(canvasDir, recursive: true);
            }

            throw;
        }
    }

    internal JsonArray ListCanvases(string? lifecycle = null, string? threadId = null)
    {
        EnsureRoot();
        var records = new JsonArray();
        var lifecycles = lifecycle is null ? Lifecycles : [lifecycle];
        var cleanThread = string.IsNullOrWhiteSpace(threadId) ? null : threadId.Trim();

        foreach (var item in lifecycles)
        {
            if (!Lifecycles.Contains(item))
            {
                throw new CanvasValidationError("Lifecycle must be one of ['active', 'archived'].");
            }

            var baseDir = LifecycleDir(item);
            foreach (var dir in Directory.GetDirectories(baseDir).OrderBy(x => x, StringComparer.OrdinalIgnoreCase))
            {
                var metadataFile = Path.Combine(dir, "canvas.json");
                if (!File.Exists(metadataFile))
                {
                    continue;
                }

                try
                {
                    var metadata = JsonUtil.ReadObject(metadataFile);
                    if (cleanThread is not null)
                    {
                        var associated = JsonUtil.StringList(metadata["associatedThreads"]);
                        if (!associated.Contains(cleanThread))
                        {
                            continue;
                        }
                    }

                    records.Add(metadata.DeepClone());
                }
                catch (Exception)
                {
                    if (cleanThread is null)
                    {
                        records.Add(new JsonObject { ["id"] = Path.GetFileName(dir), ["lifecycle"] = item, ["invalid"] = true });
                    }
                }
            }
        }

        return records;
    }

    internal JsonObject GetCanvas(string canvasId, string? lifecycle = null) => JsonUtil.ReadObject(MetadataPath(canvasId, lifecycle));

    internal JsonObject UpdateState(string canvasId, JsonObject updates, string? lifecycle = "active")
    {
        var metadataFile = MetadataPath(canvasId, lifecycle);
        var canvasDir = Path.GetDirectoryName(metadataFile)!;
        var stateFile = Path.Combine(canvasDir, "state.json");
        var state = File.Exists(stateFile) ? JsonUtil.ReadObject(stateFile) : new JsonObject();
        foreach (var kv in updates.ToList())
        {
            state[kv.Key] = kv.Value?.DeepClone();
        }

        var now = UtcNow();
        state["updated_at"] = now;
        JsonUtil.WriteObject(stateFile, state);

        var metadata = JsonUtil.ReadObject(metadataFile);
        metadata["updated_at"] = now;
        JsonUtil.WriteObject(metadataFile, metadata);
        return new JsonObject { ["metadata"] = metadata.DeepClone(), ["state"] = state.DeepClone() };
    }

    internal JsonObject ArchiveCanvas(string canvasId)
    {
        EnsureRoot();
        var id = NormalizeCanvasId(canvasId);
        var source = Path.Combine(Active, id);
        var target = Path.Combine(Archived, id);
        if (!Directory.Exists(source))
        {
            throw new CanvasValidationError($"Active canvas not found: {id}");
        }
        if (Directory.Exists(target))
        {
            throw new CanvasValidationError($"Archived canvas already exists: {id}");
        }

        var validation = ValidateCanvas(id, "active");
        if (!validation["valid"]!.GetValue<bool>())
        {
            throw new CanvasValidationError(string.Join("; ", JsonUtil.StringList(validation["errors"])));
        }

        Directory.Move(source, target);
        var metadataFile = Path.Combine(target, "canvas.json");
        var metadata = JsonUtil.ReadObject(metadataFile);
        metadata["lifecycle"] = "archived";
        metadata["storage_path"] = target;
        metadata["updated_at"] = UtcNow();
        JsonUtil.WriteObject(metadataFile, metadata);
        return metadata;
    }

    internal JsonObject AssociateThread(string canvasId, string threadId, string? lifecycle = "active")
    {
        threadId = threadId.Trim();
        if (threadId.Length == 0)
        {
            throw new CanvasValidationError("threadId cannot be empty.");
        }

        var validation = ValidateCanvas(canvasId, lifecycle);
        if (!validation["valid"]!.GetValue<bool>())
        {
            throw new CanvasValidationError(string.Join("; ", JsonUtil.StringList(validation["errors"])));
        }

        var metadataFile = MetadataPath(canvasId, lifecycle);
        var metadata = JsonUtil.ReadObject(metadataFile);
        if (!JsonUtil.IsStringArray(metadata["associatedThreads"]))
        {
            throw new CanvasValidationError("associatedThreads must be an array of non-empty strings");
        }

        var associated = JsonUtil.StringList(metadata["associatedThreads"]);
        if (!associated.Contains(threadId))
        {
            associated.Add(threadId);
        }

        metadata["associatedThreads"] = JsonUtil.StringArray(associated);
        metadata["last_updated_from_thread"] = threadId;
        metadata["updated_at"] = UtcNow();
        JsonUtil.WriteObject(metadataFile, metadata);
        return metadata;
    }

    internal JsonObject PromoteCanvas(string canvasId, string target, string reference, string note = "")
    {
        var metadataFile = MetadataPath(canvasId, "active");
        if (string.IsNullOrWhiteSpace(target))
        {
            throw new CanvasValidationError("target must be a non-empty string");
        }
        if (string.IsNullOrWhiteSpace(reference))
        {
            throw new CanvasValidationError("reference must be a non-empty string");
        }

        var validation = ValidateCanvas(canvasId, "active");
        if (!validation["valid"]!.GetValue<bool>())
        {
            throw new CanvasValidationError(string.Join("; ", JsonUtil.StringList(validation["errors"])));
        }

        var metadata = JsonUtil.ReadObject(metadataFile);
        var allowed = JsonUtil.StringList(metadata["promotion_targets"]);
        if (!allowed.Contains(target))
        {
            throw new CanvasValidationError($"Promotion target '{target}' is not allowed for this canvas.");
        }

        var now = UtcNow();
        var promotion = new JsonObject
        {
            ["target"] = target,
            ["reference"] = reference,
            ["note"] = note,
            ["promoted_at"] = now
        };
        var promotions = metadata["promotions"] as JsonArray ?? new JsonArray();
        promotions.Add(promotion);
        metadata["promotions"] = promotions;
        metadata["updated_at"] = now;
        JsonUtil.WriteObject(metadataFile, metadata);

        var notesFile = Path.Combine(Path.GetDirectoryName(metadataFile)!, "notes.md");
        File.AppendAllText(notesFile, $"\n## Promotion\n\n- {now}: {target} -> {reference}{(string.IsNullOrEmpty(note) ? "" : $" ({note})")}\n");
        return metadata;
    }

    internal JsonObject ValidateCanvas(string canvasId, string? lifecycle = null)
    {
        var metadataFile = MetadataPath(canvasId, lifecycle);
        var canvasDir = Path.GetDirectoryName(metadataFile)!;
        var errors = new List<string>();
        var warnings = new List<string>();
        JsonObject metadata;
        try
        {
            metadata = JsonUtil.ReadObject(metadataFile);
        }
        catch (JsonException exc)
        {
            return ValidationResult(Path.GetFileName(canvasDir), false, [$"Invalid JSON: {exc.Message}"], [], new JsonObject());
        }

        foreach (var field in new[] { "id", "kind", "lifecycle", "authority", "scope", "storage_path", "state_files" })
        {
            if (!metadata.ContainsKey(field))
            {
                errors.Add($"Missing metadata field: {field}");
            }
        }

        var id = metadata.StringValue("id");
        if (string.IsNullOrWhiteSpace(id))
        {
            errors.Add("id must be a non-empty string");
        }
        else if (id != Path.GetFileName(canvasDir))
        {
            errors.Add("id must match the canvas directory");
        }
        else if (NormalizeCanvasId(id) != id)
        {
            errors.Add("id must be normalized");
        }

        if (metadata.StringValue("kind") != "canvas")
        {
            errors.Add("kind must be 'canvas'");
        }

        var metaLifecycle = metadata.StringValue("lifecycle");
        if (metaLifecycle is null || !Lifecycles.Contains(metaLifecycle))
        {
            errors.Add("lifecycle must be active or archived");
        }
        else
        {
            var actual = Path.GetFileName(Path.GetDirectoryName(canvasDir)!);
            if (Lifecycles.Contains(actual) && metaLifecycle != actual)
            {
                errors.Add($"lifecycle must match canvas location: {actual}");
            }
        }

        var scope = metadata.StringValue("scope");
        if (scope is null || !Scopes.Contains(scope))
        {
            errors.Add("scope must be one of ['project', 'repo', 'thread', 'user']");
        }

        var storagePath = metadata.StringValue("storage_path");
        if (string.IsNullOrWhiteSpace(storagePath))
        {
            errors.Add("storage_path must be a non-empty string");
        }
        else if (!string.Equals(Path.GetFullPath(storagePath), Path.GetFullPath(canvasDir), StringComparison.OrdinalIgnoreCase))
        {
            errors.Add("storage_path must match the canvas directory");
        }

        ValidateStringArrayField(metadata, "associatedThreads", errors);
        ValidateStringArrayField(metadata, "promotion_targets", errors);
        ValidatePromotions(metadata["promotions"], errors);

        foreach (var field in new[] { "state_files", "shared_state" })
        {
            if (!JsonUtil.IsStringArray(metadata[field]))
            {
                errors.Add($"{field} must be an array of non-empty strings");
                continue;
            }
            foreach (var filename in JsonUtil.StringList(metadata[field]))
            {
                if (Path.IsPathRooted(filename) || filename.Split(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar).Contains(".."))
                {
                    errors.Add($"State file must be relative to the canvas: {filename}");
                    continue;
                }
                if (!File.Exists(Path.Combine(canvasDir, filename)))
                {
                    errors.Add($"Missing state file: {filename.Replace('\\', '/')}");
                }
            }
        }

        if (!File.Exists(Path.Combine(canvasDir, "README.md")))
        {
            warnings.Add("README.md is missing");
        }
        if (!metadata.ContainsKey("agent_actions") || (metadata["agent_actions"] as JsonArray)?.Count == 0)
        {
            warnings.Add("agent_actions is empty");
        }
        if (!metadata.ContainsKey("human_actions") || (metadata["human_actions"] as JsonArray)?.Count == 0)
        {
            warnings.Add("human_actions is empty");
        }

        return ValidationResult(id ?? Path.GetFileName(canvasDir), errors.Count == 0, errors, warnings, metadata);
    }

    internal JsonObject ExportHtml(string canvasId, string? lifecycle = null, string? output = null)
    {
        var metadataFile = MetadataPath(canvasId, lifecycle);
        var canvasDir = Path.GetDirectoryName(metadataFile)!;
        var metadata = JsonUtil.ReadObject(metadataFile);
        var stateFile = Path.Combine(canvasDir, "state.json");
        var notesFile = Path.Combine(canvasDir, "notes.md");
        var state = File.Exists(stateFile) ? JsonUtil.ReadObject(stateFile) : new JsonObject();
        var notes = File.Exists(notesFile) ? File.ReadAllText(notesFile) : "";
        var validation = ValidateCanvas(Path.GetFileName(canvasDir), Path.GetFileName(Path.GetDirectoryName(canvasDir)!));

        var outputPath = string.IsNullOrWhiteSpace(output) ? Path.Combine(canvasDir, "canvas.html") : PathUtil.ExpandPath(output);
        if (!Path.IsPathRooted(outputPath))
        {
            outputPath = Path.Combine(canvasDir, outputPath);
        }
        outputPath = Path.GetFullPath(outputPath);
        Directory.CreateDirectory(Path.GetDirectoryName(outputPath)!);
        File.Copy(Path.Combine(PathUtil.PluginRoot(), "skills", "canvas", "templates", "canvas-viewer.html"), outputPath, overwrite: true);
        var dataPath = Path.Combine(Path.GetDirectoryName(outputPath)!, "canvas-data.js");
        File.WriteAllText(
            dataPath,
            "window.CANVAS_DATA = " + JsonUtil.Stringify(new Dictionary<string, object?>
            {
                ["metadata"] = metadata,
                ["state"] = state,
                ["notes"] = notes,
                ["validation"] = validation
            }) + ";" + Environment.NewLine);

        return new JsonObject
        {
            ["id"] = Path.GetFileName(canvasDir),
            ["lifecycle"] = Path.GetFileName(Path.GetDirectoryName(canvasDir)!),
            ["html_path"] = outputPath,
            ["data_path"] = dataPath,
            ["valid"] = validation["valid"]!.GetValue<bool>(),
            ["warnings"] = validation["warnings"]!.DeepClone()
        };
    }

    internal string MetadataPath(string canvasId, string? lifecycle = null)
    {
        EnsureRoot();
        var id = NormalizeCanvasId(canvasId);
        if (!string.IsNullOrWhiteSpace(lifecycle))
        {
            if (!Lifecycles.Contains(lifecycle))
            {
                throw new CanvasValidationError("Lifecycle must be one of ['active', 'archived'].");
            }
            var path = Path.Combine(LifecycleDir(lifecycle), id, "canvas.json");
            if (File.Exists(path))
            {
                return path;
            }
            throw new CanvasValidationError($"Canvas not found: {id}");
        }

        foreach (var baseDir in new[] { Active, Archived })
        {
            var path = Path.Combine(baseDir, id, "canvas.json");
            if (File.Exists(path))
            {
                return path;
            }
        }

        throw new CanvasValidationError($"Canvas not found: {id}");
    }

    internal string LifecycleDir(string lifecycle) => lifecycle == "active" ? Active : Archived;

    internal static string NormalizeCanvasId(string value)
    {
        var normalized = Regex.Replace(value.Trim().ToLowerInvariant(), "[^a-z0-9]+", "-").Trim('-');
        normalized = Regex.Replace(normalized, "-+", "-");
        if (normalized.Length == 0)
        {
            throw new CanvasValidationError("Canvas id cannot be empty after normalization.");
        }
        if (normalized.Length > 96)
        {
            throw new CanvasValidationError("Canvas id must be 96 characters or fewer.");
        }

        return normalized;
    }

    internal static string UtcNow() => DateTimeOffset.UtcNow.ToString("yyyy-MM-ddTHH:mm:ss+00:00");

    private static List<string> CleanList(IEnumerable<string>? values, IEnumerable<string> fallback)
    {
        var source = values ?? fallback;
        var clean = new List<string>();
        foreach (var value in source)
        {
            var item = value.Trim();
            if (item.Length > 0 && !clean.Contains(item))
            {
                clean.Add(item);
            }
        }
        return clean;
    }

    private static string AnchorFingerprint(string anchor)
    {
        if (string.IsNullOrWhiteSpace(anchor))
        {
            return "";
        }
        try
        {
            return "path:" + Path.GetFullPath(PathUtil.ExpandPath(anchor));
        }
        catch
        {
            return "text:" + anchor.Trim();
        }
    }

    private static string ReadmeText(JsonObject metadata)
    {
        var human = string.Join("\n", JsonUtil.StringList(metadata["human_actions"]).Select(x => $"- `{x}`"));
        var agent = string.Join("\n", JsonUtil.StringList(metadata["agent_actions"]).Select(x => $"- `{x}`"));
        return $"# {metadata.StringValue("title")}\n\nCanvas id: `{metadata.StringValue("id")}`\n\nScope: `{metadata.StringValue("scope")}`\n\nAnchor: `{metadata.StringValue("anchor")}`\n\n## Human Actions\n\n{human}\n\n## Agent Actions\n\n{agent}\n";
    }

    private static void ValidateStringArrayField(JsonObject metadata, string field, List<string> errors)
    {
        if (metadata.ContainsKey(field) && !JsonUtil.IsStringArray(metadata[field]))
        {
            errors.Add($"{field} must be an array of non-empty strings");
        }
    }

    private static void ValidatePromotions(JsonNode? node, List<string> errors)
    {
        if (node is null)
        {
            return;
        }
        if (node is not JsonArray array)
        {
            errors.Add("promotions must be an array of promotion records");
            return;
        }
        for (var i = 0; i < array.Count; i++)
        {
            if (array[i] is not JsonObject promotion)
            {
                errors.Add($"promotions[{i}] must be an object");
                continue;
            }
            foreach (var field in new[] { "target", "reference", "promoted_at" })
            {
                if (string.IsNullOrWhiteSpace(promotion.StringValue(field)))
                {
                    errors.Add($"promotions[{i}].{field} must be a non-empty string");
                }
            }
            if (promotion.ContainsKey("note") && promotion["note"] is not null)
            {
                try
                {
                    promotion["note"]!.GetValue<string>();
                }
                catch
                {
                    errors.Add($"promotions[{i}].note must be a string");
                }
            }
        }
    }

    private static JsonObject ValidationResult(string id, bool valid, List<string> errors, List<string> warnings, JsonObject metadata)
    {
        return new JsonObject
        {
            ["id"] = id,
            ["valid"] = valid,
            ["errors"] = JsonUtil.StringArray(errors),
            ["warnings"] = JsonUtil.StringArray(warnings),
            ["metadata"] = metadata.DeepClone()
        };
    }
}
