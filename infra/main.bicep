// Subscription-level entry point for azd: creates the resource group and deploys all application resources.
// Parameters come from infra/main.parameters.json, populated from the azd environment.
// Outputs are written back to the azd environment and used by the deploy step.
targetScope = 'subscription'

@minLength(1)
@maxLength(40)
@description('azd environment name, used to name the resource group and tag resources.')
param environmentName string

@minLength(1)
@description('Azure region for all resources. Choose one with Foundry model capacity, for example eastus2 or swedencentral.')
param location string

@description('Object id of the developer running azd, granted model access for local runs. Empty to skip.')
param principalId string = ''

@description('Container image for the web service; empty uses a placeholder until azd deploys the real image.')
param webImageName string = ''

@description('Foundry model to deploy.')
param modelName string = 'gpt-4.1-mini'

@description('Model version to deploy.')
param modelVersion string = '2025-04-14'

@description('Deployment capacity in thousands of tokens per minute.')
param modelCapacity int = 30

var tags = { 'azd-env-name': environmentName }

resource resourceGroup 'Microsoft.Resources/resourceGroups@2024-03-01' = {
  name: 'rg-${environmentName}'
  location: location
  tags: tags
}

module resources 'resources.bicep' = {
  name: 'resources'
  scope: resourceGroup
  params: {
    location: location
    environmentName: environmentName
    tags: tags
    principalId: principalId
    webImageName: webImageName
    modelName: modelName
    modelVersion: modelVersion
    modelCapacity: modelCapacity
  }
}

output AZURE_RESOURCE_GROUP string = resourceGroup.name
output AZURE_CONTAINER_REGISTRY_ENDPOINT string = resources.outputs.registryLoginServer
output AZURE_OPENAI_ENDPOINT string = resources.outputs.openAiEndpoint
output AZURE_FOUNDRY_PROJECT string = resources.outputs.foundryProjectName
output AZURE_MODEL_DEPLOYMENT string = resources.outputs.modelDeploymentName
output SERVICE_WEB_URI string = resources.outputs.webUri
