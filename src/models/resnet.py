import torch
import torch.nn as nn


# Define the Residual Block
class ResidualBlock(nn.Module):
    def __init__(self, in_channels, out_channels, stride=1):
        super(ResidualBlock, self).__init__()

        self.conv1 = nn.Conv2d(in_channels, out_channels, kernel_size=3, stride=stride, padding=1, bias=False)
        self.bn1 = nn.BatchNorm2d(out_channels)
        self.relu = nn.ReLU(inplace=True)

        self.conv2 = nn.Conv2d(out_channels, out_channels, kernel_size=3, stride=1, padding=1, bias=False)
        self.bn2 = nn.BatchNorm2d(out_channels)

        self.shortcut = nn.Sequential()
        if stride != 1 or in_channels != out_channels:
            self.shortcut = nn.Sequential(
                nn.Conv2d(in_channels, out_channels, kernel_size=1, stride=stride, bias=False),
                nn.BatchNorm2d(out_channels)
            )

    def forward(self, x):
        out = self.relu(self.bn1(self.conv1(x)))
        out = self.bn2(self.conv2(out))
        out += self.shortcut(x)
        out = self.relu(out)
        return out


# Define the ResNet9
class ResNet9(nn.Module):
    def __init__(self, block, num_classes=10):
        super(ResNet9, self).__init__()
        self.in_channels = 64

        self.conv1 = nn.Conv2d(3, 64, kernel_size=3, stride=1, padding=1, bias=False)
        self.bn1 = nn.BatchNorm2d(64)
        self.relu = nn.ReLU(inplace=True)

        self.layer1 = self._make_layer(block, 64, stride=1)
        self.layer2 = self._make_layer(block, 128, stride=2)

        self.avg_pool = nn.AdaptiveAvgPool2d((1, 1))
        self.fc = nn.Linear(128, num_classes)

    def _make_layer(self, block, out_channels, stride):
        layer = block(self.in_channels, out_channels, stride)
        self.in_channels = out_channels
        return layer

    def forward(self, x):
        features = self.extract_features(x)
        output = self.fc(features)    
        return output

    def extract_features(self, x):
        out = self.relu(self.bn1(self.conv1(x)))
        out = self.layer1(out)
        out = self.layer2(out)
        features = self.avg_pool(out)
        features = features.view(features.size(0), -1)
        return features
    

    def get_weights(self, nclasses, nlayers):
        shared = torch.empty(0)
        distinct = []
        for l in nlayers:
            if l == 1:
                w = self.fc.weight.data
                b = self.fc.bias.data
                for i in range(nclasses):
                    class_weights = torch.cat((w[i], b[i].view(1)), 0)
                    distinct.append(class_weights)
            elif l == 2:
                shared = torch.cat((shared, self.layer2.conv2.weight.data.view(-1)), 0)
                shared = torch.cat((shared, self.layer2.bn2.weight.data.view(-1)), 0)
            elif l == 3:
                shared = torch.cat((shared, self.layer1.conv2.weight.data.view(-1)), 0)
                shared = torch.cat((shared, self.layer1.bn2.weight.data.view(-1)), 0)
            else:
                raise ValueError(f'Unknown layer: {l}')
        return (distinct, shared)


    def set_weights(self, distinct, shared, nlayers):
        for l in nlayers:
            if l == 1:
                for i in range(distinct.size(0)):
                    self.fc.weight.data[i] = distinct[i][:-1]
                    self.fc.bias.data[i] = distinct[i][-1]
            elif l == 2:
                self.layer2.conv2.weight.data = shared[:self.layer2.conv2.weight.numel()].view(self.layer2.conv2.weight.size())
                shared = shared[self.layer2.conv2.weight.numel():]
                self.layer2.bn2.weight.data = shared[:self.layer2.bn2.weight.numel()].view(self.layer2.bn2.weight.size())
                shared = shared[self.layer2.bn2.weight.numel():]
            elif l == 3:
                self.layer1.conv2.weight.data = shared[:self.layer1.conv2.weight.numel()].view(self.layer1.conv2.weight.size())
                shared = shared[self.layer1.conv2.weight.numel():]
                self.layer1.bn2.weight.data = shared[:self.layer1.bn2.weight.numel()].view(self.layer1.bn2.weight.size())
        return


# Define the ResNet18
class ResNet18(nn.Module):
    def __init__(self, block, num_classes=10):
        super(ResNet18, self).__init__()
        self.in_channels = 64

        self.conv1 = nn.Conv2d(3, 64, kernel_size=7, stride=2, padding=3, bias=False)
        self.bn1 = nn.BatchNorm2d(64)
        self.relu = nn.ReLU(inplace=True)
        self.maxpool = nn.MaxPool2d(kernel_size=3, stride=2, padding=1)

        self.layer1 = self._make_layer(block, 64, stride=1)
        self.layer2 = self._make_layer(block, 128, stride=2)
        self.layer3 = self._make_layer(block, 256, stride=2)
        self.layer4 = self._make_layer(block, 512, stride=2)

        self.avg_pool = nn.AdaptiveAvgPool2d((1, 1))
        self.fc = nn.Linear(512, num_classes)
        

    def _make_layer(self, block, out_channels, stride):
        layer = block(self.in_channels, out_channels, stride)
        self.in_channels = out_channels
        return layer

    def forward(self, x):
        features = self.extract_features(x)
        out = self.fc(features)
        return out

    def extract_features(self, x):
        out = self.relu(self.bn1(self.conv1(x)))
        out = self.maxpool(out)
        out = self.layer1(out)
        out = self.layer2(out)
        out = self.layer3(out)
        out = self.layer4(out)
        features = self.avg_pool(out)
        features = features.view(features.size(0), -1)
        return features


    def get_weights(self, nclasses, nlayers):
        # Initialize `shared` tensor on the same device as the model.
        device = 'cuda' if torch.cuda.is_available() else 'cpu'
        shared = torch.empty(0, device=device)
        
        distinct = []
        for l in nlayers:
            if l == 1:
                w = self.fc.weight.data
                b = self.fc.bias.data
                for i in range(nclasses):
                    class_weights = torch.cat((w[i], b[i].view(1)), 0)
                    distinct.append(class_weights)
            elif l == 2:
                shared = torch.cat((shared, self.layer4.conv2.weight.data.view(-1).to(device)), 0)
                shared = torch.cat((shared, self.layer4.bn2.weight.data.view(-1).to(device)), 0)
            elif l == 3:
                shared = torch.cat((shared, self.layer3.conv2.weight.data.view(-1).to(device)), 0)
                shared = torch.cat((shared, self.layer3.bn2.weight.data.view(-1).to(device)), 0)
            elif l == 4:
                shared = torch.cat((shared, self.layer2.conv2.weight.data.view(-1).to(device)), 0)
                shared = torch.cat((shared, self.layer2.bn2.weight.data.view(-1).to(device)), 0)
            elif l == 5:
                shared = torch.cat((shared, self.layer1.conv2.weight.data.view(-1).to(device)), 0)
                shared = torch.cat((shared, self.layer1.bn2.weight.data.view(-1).to(device)), 0)
            else:
                raise ValueError(f'Unknown layer: {l}')
        
        if distinct != []:
            distinct = torch.stack([d.to(device) for d in distinct])
        
        return (distinct, shared)

    

    def set_weights(self, distinct, shared, nlayers):
        for l in nlayers:
            if l == 1:
                for i in range(distinct.size(0)):
                    self.fc.weight.data[i] = distinct[i][:-1]
                    self.fc.bias.data[i] = distinct[i][-1]
            elif l == 2:
                self.layer4.conv2.weight.data = shared[:self.layer4.conv2.weight.numel()].view(self.layer4.conv2.weight.size())
                shared = shared[self.layer4.conv2.weight.numel():]
                self.layer4.bn2.weight.data = shared[:self.layer4.bn2.weight.numel()].view(self.layer4.bn2.weight.size())
                shared = shared[self.layer4.bn2.weight.numel():]
            elif l == 3:
                self.layer3.conv2.weight.data = shared[:self.layer3.conv2.weight.numel()].view(self.layer3.conv2.weight.size())
                shared = shared[self.layer3.conv2.weight.numel():]
                self.layer3.bn2.weight.data = shared[:self.layer3.bn2.weight.numel()].view(self.layer3.bn2.weight.size())
                shared = shared[self.layer3.bn2.weight.numel():]
            elif l == 4:
                self.layer2.conv2.weight.data = shared[:self.layer2.conv2.weight.numel()].view(self.layer2.conv2.weight.size())
                shared = shared[self.layer2.conv2.weight.numel():]
                self.layer2.bn2.weight.data = shared[:self.layer2.bn2.weight.numel()].view(self.layer2.bn2.weight.size())
                shared = shared[self.layer2.bn2.weight.numel():]
            elif l == 5:
                self.layer1.conv2.weight.data = shared[:self.layer1.conv2.weight.numel()].view(self.layer1.conv2.weight.size())
                shared = shared[self.layer1.conv2.weight.numel():]
                self.layer1.bn2.weight.data = shared[:self.layer1.bn2.weight.numel()].view(self.layer1.bn2.weight.size())
        return


# Define the ResNet18
class ResNetCustom(nn.Module):
    def __init__(self, block, num_classes=10):
        super(ResNetCustom, self).__init__()
        self.in_channels = 64

        self.conv1 = nn.Conv2d(3, 64, kernel_size=7, stride=2, padding=3, bias=False)
        self.bn1 = nn.BatchNorm2d(64)
        self.relu = nn.ReLU(inplace=True)
        self.maxpool = nn.MaxPool2d(kernel_size=3, stride=2, padding=1)

        self.layer1 = self._make_layer(block, 32, stride=1)
        self.layer2 = self._make_layer(block, 64, stride=2)
        self.layer3 = self._make_layer(block, 128, stride=2)
        self.layer4 = self._make_layer(block, 128, stride=2)

        self.avg_pool = nn.AdaptiveAvgPool2d((1, 1))
        self.fc = nn.Linear(128, num_classes)

    def _make_layer(self, block, out_channels, stride):
        layer = block(self.in_channels, out_channels, stride)
        self.in_channels = out_channels
        return layer

    def forward(self, x):
        features = self.extract_features(x)
        out = self.fc(features)
        return out

    def extract_features(self, x):
        out = self.relu(self.bn1(self.conv1(x)))
        out = self.maxpool(out)
        out = self.layer1(out)
        out = self.layer2(out)
        out = self.layer3(out)
        out = self.layer4(out)
        features = self.avg_pool(out)
        features = features.view(features.size(0), -1)
        return features


    def get_weights(self, nclasses, nlayers):
        # Initialize `shared` tensor on the same device as the model.
        device = 'cuda' if torch.cuda.is_available() else 'cpu'
        shared = torch.empty(0, device=device)
        
        distinct = []
        for l in nlayers:
            if l == 1:
                w = self.fc.weight.data
                b = self.fc.bias.data
                for i in range(nclasses):
                    class_weights = torch.cat((w[i], b[i].view(1)), 0)
                    distinct.append(class_weights)
            elif l == 2:
                shared = torch.cat((shared, self.layer4.conv2.weight.data.view(-1).to(device)), 0)
                shared = torch.cat((shared, self.layer4.bn2.weight.data.view(-1).to(device)), 0)
            elif l == 3:
                shared = torch.cat((shared, self.layer3.conv2.weight.data.view(-1).to(device)), 0)
                shared = torch.cat((shared, self.layer3.bn2.weight.data.view(-1).to(device)), 0)
            elif l == 4:
                shared = torch.cat((shared, self.layer2.conv2.weight.data.view(-1).to(device)), 0)
                shared = torch.cat((shared, self.layer2.bn2.weight.data.view(-1).to(device)), 0)
            elif l == 5:
                shared = torch.cat((shared, self.layer1.conv2.weight.data.view(-1).to(device)), 0)
                shared = torch.cat((shared, self.layer1.bn2.weight.data.view(-1).to(device)), 0)
            else:
                raise ValueError(f'Unknown layer: {l}')
        
        if distinct != []:
            distinct = torch.stack([d.to(device) for d in distinct])
        
        return (distinct, shared)

    

    def set_weights(self, distinct, shared, nlayers):
        for l in nlayers:
            if l == 1:
                for i in range(distinct.size(0)):
                    self.fc.weight.data[i] = distinct[i][:-1]
                    self.fc.bias.data[i] = distinct[i][-1]
            elif l == 2:
                self.layer4.conv2.weight.data = shared[:self.layer4.conv2.weight.numel()].view(self.layer4.conv2.weight.size())
                shared = shared[self.layer4.conv2.weight.numel():]
                self.layer4.bn2.weight.data = shared[:self.layer4.bn2.weight.numel()].view(self.layer4.bn2.weight.size())
                shared = shared[self.layer4.bn2.weight.numel():]
            elif l == 3:
                self.layer3.conv2.weight.data = shared[:self.layer3.conv2.weight.numel()].view(self.layer3.conv2.weight.size())
                shared = shared[self.layer3.conv2.weight.numel():]
                self.layer3.bn2.weight.data = shared[:self.layer3.bn2.weight.numel()].view(self.layer3.bn2.weight.size())
                shared = shared[self.layer3.bn2.weight.numel():]
            elif l == 4:
                self.layer2.conv2.weight.data = shared[:self.layer2.conv2.weight.numel()].view(self.layer2.conv2.weight.size())
                shared = shared[self.layer2.conv2.weight.numel():]
                self.layer2.bn2.weight.data = shared[:self.layer2.bn2.weight.numel()].view(self.layer2.bn2.weight.size())
                shared = shared[self.layer2.bn2.weight.numel():]
            elif l == 5:
                self.layer1.conv2.weight.data = shared[:self.layer1.conv2.weight.numel()].view(self.layer1.conv2.weight.size())
                shared = shared[self.layer1.conv2.weight.numel():]
                self.layer1.bn2.weight.data = shared[:self.layer1.bn2.weight.numel()].view(self.layer1.bn2.weight.size())
        return




if __name__ == '__main__':
    model = ResNet9(ResidualBlock)
    img = torch.randn(2, 3, 224, 224)  # fake batch of RGB images
    output = model(img)
    print(output.shape)
    print(output)
