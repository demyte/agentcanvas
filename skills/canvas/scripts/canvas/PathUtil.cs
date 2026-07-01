namespace CanvasApp;

internal static class PathUtil
{
    internal static string PluginRoot()
    {
        var baseDir = AppContext.BaseDirectory;
        var fromBin = Path.GetFullPath(Path.Combine(baseDir, "..", "..", ".."));
        if (File.Exists(Path.Combine(fromBin, ".codex-plugin", "plugin.json")))
        {
            return fromBin;
        }

        var current = Directory.GetCurrentDirectory();
        while (!string.IsNullOrEmpty(current))
        {
            if (File.Exists(Path.Combine(current, ".codex-plugin", "plugin.json")))
            {
                return current;
            }

            var parent = Directory.GetParent(current)?.FullName;
            if (parent is null || parent == current)
            {
                break;
            }

            current = parent;
        }

        return Directory.GetCurrentDirectory();
    }

    internal static string ExpandPath(string value)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            return value;
        }

        if (value == "~")
        {
            return Environment.GetFolderPath(Environment.SpecialFolder.UserProfile);
        }

        if (value.StartsWith("~/", StringComparison.Ordinal) || value.StartsWith("~\\", StringComparison.Ordinal))
        {
            return Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.UserProfile), value[2..]);
        }

        return value;
    }

    internal static string FullPath(string value) => Path.GetFullPath(ExpandPath(value));
}
