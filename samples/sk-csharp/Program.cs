using Microsoft.SemanticKernel;
using Microsoft.SemanticKernel.Plugins.OpenApi;
using System.Net.Http.Headers;
using Microsoft.Identity.Client;

static async Task<string> GetCallerTokenAsync()
{
    var tenantId = Environment.GetEnvironmentVariable("AZURE_TENANT_ID")!;
    var clientId = Environment.GetEnvironmentVariable("CALLER_AGENT_CLIENT_ID")!;
    var clientSecret = Environment.GetEnvironmentVariable("CALLER_AGENT_CLIENT_SECRET")!;
    var audienceScope = Environment.GetEnvironmentVariable("FUNCTION_AUDIENCE_SCOPE")!;
    var app = ConfidentialClientApplicationBuilder.Create(clientId)
        .WithClientSecret(clientSecret)
        .WithAuthority($"https://login.microsoftonline.com/{tenantId}")
        .Build();
    var result = await app.AcquireTokenForClient(new[] { audienceScope }).ExecuteAsync();
    return result.AccessToken;
}

var builder = Kernel.CreateBuilder();
builder.AddAzureOpenAIChatCompletion(
    deploymentName: Environment.GetEnvironmentVariable("AZURE_OPENAI_DEPLOYMENT")!,
    endpoint:       Environment.GetEnvironmentVariable("AZURE_OPENAI_ENDPOINT")!,
    apiKey:         Environment.GetEnvironmentVariable("AZURE_OPENAI_API_KEY")!
);
var kernel = builder.Build();

var http = new HttpClient { BaseAddress = new Uri(Environment.GetEnvironmentVariable("APIM_BASE_URL") ?? "http://localhost:8080") };
http.DefaultRequestHeaders.Accept.Add(new MediaTypeWithQualityHeaderValue("application/json"));

var execParams = new OpenApiFunctionExecutionParameters
{
    HttpClient = http,
    EnableDynamicOperationPayloads = true,
    OperationHeadersFactory = async (opName) => new Dictionary<string, string>
    {
        ["Authorization"] = $"Bearer {await GetCallerTokenAsync()}",
        ["x-purpose"] = opName == "calendar_freebusy" ? "meeting_scheduling" : "project_collab"
    }
};

await kernel.ImportPluginFromOpenApiAsync("MeshTools", "agents/personal-agent-tools.openapi.yaml", execParams);

var args = new KernelArguments {
    ["caller_oid"] = "11111111-1111-1111-1111-111111111111",
    ["purpose"]    = "meeting_scheduling",
    ["range_start"]= "2025-10-01T00:00:00Z",
    ["range_end"]  = "2025-10-07T23:59:59Z",
    ["user_delegated_jwt"] = Environment.GetEnvironmentVariable("B_USER_DELEGATED_JWT") ?? "fake"
};
var result = await kernel.InvokeAsync("MeshTools","calendar_freebusy", args);
Console.WriteLine(result.GetValue<string>());
