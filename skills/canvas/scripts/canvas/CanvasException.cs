namespace CanvasApp;

internal class CanvasException(string message) : Exception(message);

internal sealed class CanvasValidationError(string message) : CanvasException(message);
