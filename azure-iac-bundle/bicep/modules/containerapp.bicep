
param location string
param namePrefix string
param envId string
param image string
param appInsightsConnectionString string

resource app 'Microsoft.App/containerApps@2024-02-01' = {
  name: '${namePrefix}-api'
  location: location
  identity: { type: 'SystemAssigned' }
  properties: {
    managedEnvironmentId: envId
    configuration: {
      ingress: { external: true, targetPort: 8080, transport: 'auto' }
      activeRevisionsMode: 'Single'
      environmentVariables: [
        { name: 'APPINSIGHTS_CONNECTION_STRING', value: appInsightsConnectionString }
        { name: 'REGION', value: location }
      ]
    }
    template: {
      containers: [ { name: 'api', image: image, resources: { cpu: 1.0, memory: '2Gi' } } ]
      scale: {
        minReplicas: 1
        maxReplicas: 20
        rules: [ { name: 'http', http: { concurrentRequests: 50 } } ]
      }
    }
  }
}
output appUrl string = app.properties.configuration.ingress.fqdn
