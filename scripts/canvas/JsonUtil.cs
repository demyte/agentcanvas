using System.Text.Encodings.Web;
using System.Text.Json;
using System.Text.Json.Nodes;

namespace CanvasApp;

internal static class JsonUtil
{
    internal static readonly JsonSerializerOptions Options = new()
    {
        WriteIndented = true,
        Encoder = JavaScriptEncoder.UnsafeRelaxedJsonEscaping
    };

    internal static string Stringify(object? value) => JsonSerializer.Serialize(value, Options);

    internal static void WriteStdout(object? value) => Console.WriteLine(Stringify(value));

    internal static JsonObject ReadObject(string path)
    {
        var node = JsonNode.Parse(File.ReadAllText(path));
        return node as JsonObject ?? throw new CanvasValidationError($"JSON file must contain an object: {path}");
    }

    internal static void WriteObject(string path, JsonObject data)
    {
        Directory.CreateDirectory(Path.GetDirectoryName(path)!);
        File.WriteAllText(path, data.ToJsonString(Options) + Environment.NewLine);
    }

    internal static string? StringValue(this JsonObject obj, string key)
    {
        return obj.TryGetPropertyValue(key, out var value) ? value?.GetValue<string>() : null;
    }

    internal static bool IsStringArray(JsonNode? node, bool allowEmptyItems = false)
    {
        if (node is not JsonArray array)
        {
            return false;
        }

        foreach (var item in array)
        {
            if (item is null)
            {
                return false;
            }

            try
            {
                var value = item.GetValue<string>();
                if (!allowEmptyItems && string.IsNullOrWhiteSpace(value))
                {
                    return false;
                }
            }
            catch (InvalidOperationException)
            {
                return false;
            }
        }

        return true;
    }

    internal static JsonArray StringArray(IEnumerable<string> values)
    {
        var array = new JsonArray();
        foreach (var value in values)
        {
            array.Add(value);
        }

        return array;
    }

    internal static List<string> StringList(JsonNode? node)
    {
        var result = new List<string>();
        if (node is not JsonArray array)
        {
            return result;
        }

        foreach (var item in array)
        {
            if (item is not null)
            {
                result.Add(item.GetValue<string>());
            }
        }

        return result;
    }
}
