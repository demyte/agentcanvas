#:sdk Microsoft.NET.Sdk.Web
#:property TargetFramework=net10.0
#:property PublishAot=false
#:property PublishSingleFile=true
#:property SelfContained=false
#:include canvas/**/*.cs

return await CanvasApp.Cli.RunAsync(args);
