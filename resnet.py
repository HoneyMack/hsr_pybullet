# Adapted from https://github.com/pytorch/vision/blob/master/torchvision/models/resnet.py (71322cba652b4ba7bcaa7ae5ee86f539d1ae3a2b)
import torch.nn as nn


USE_RELU = True
__all__ = ['ResNet', 'resnet18']


def conv3x3(in_planes, out_planes, stride=1, dilation=1):
    """3x3 convolution with padding"""
    return nn.Conv2d(in_planes, out_planes, kernel_size=3, stride=stride, dilation=dilation,
                     padding=dilation, bias=False)


def conv1x1(in_planes, out_planes, stride=1):
    """1x1 convolution"""
    return nn.Conv2d(in_planes, out_planes, kernel_size=1, stride=stride, bias=False)


class BasicBlock(nn.Module):
    def __init__(self, inplanes, planes, stride=1, downsample=None, dilation=1):
        super(BasicBlock, self).__init__()
        # Both self.conv1 and self.downsample layers downsample the input when stride != 1
        self.conv1 = conv3x3(inplanes, planes, stride, dilation)
        self.bn1 = nn.BatchNorm2d(planes)
        self.relu = nn.ReLU(inplace=True)
        self.conv2 = conv3x3(planes, planes)
        self.bn2 = nn.BatchNorm2d(planes)
        self.downsample = downsample
        self.stride = stride

    def forward(self, x):
        identity = x

        out = self.conv1(x)
        out = self.bn1(out)
        if USE_RELU:
            out = self.relu(out)

        out = self.conv2(out)
        out = self.bn2(out)

        if self.downsample is not None:
            identity = self.downsample(x)

        out += identity
        if USE_RELU:
            out = self.relu(out)

        return out


class ResNet(nn.Module):

    def __init__(self, block, layers, num_input_channels=3, num_classes=1000, dilation=False):
        super(ResNet, self).__init__()
        self.inplanes = 64
        self.conv1 = nn.Conv2d(num_input_channels, 64, kernel_size=7, stride=2, padding=3,
                               bias=False)
        self.bn1 = nn.BatchNorm2d(64)
        self.relu = nn.ReLU(inplace=True)
        self.maxpool = nn.MaxPool2d(kernel_size=3, stride=2, padding=1)
        self.dilation = 1 
        self.layer1 = self._make_layer(block, 64, layers[0])
        
        if dilation:
            self.layer2 = self._make_layer(block, 128, layers[1], stride=3, dilation=dilation)
            self.layer3 = self._make_layer(block, 256, layers[2], stride=3, dilation=dilation)
            self.layer4 = self._make_layer(block, 512, layers[3], stride=3, dilation=dilation)
        else:
            self.layer2 = self._make_layer(block, 128, layers[1])
            self.layer3 = self._make_layer(block, 256, layers[2])
            self.layer4 = self._make_layer(block, 512, layers[3])
        

        self.avgpool = nn.AdaptiveAvgPool2d((1, 1))
        self.fc = nn.Linear(512, num_classes)

        for m in self.modules():
            if isinstance(m, nn.Conv2d):
                nn.init.kaiming_normal_(m.weight, mode='fan_out', nonlinearity='relu')
            elif isinstance(m, nn.BatchNorm2d):
                nn.init.constant_(m.weight, 1)
                nn.init.constant_(m.bias, 0)

    def _make_layer(self, block, planes, blocks, stride=1, dilation=False):
        downsample = None
        previous_dilation = self.dilation
        if dilation:
            self.dilation *= stride
            stride = 1

        if stride != 1 or self.inplanes != planes:
            downsample = nn.Sequential(
                conv1x1(self.inplanes, planes, stride),
                nn.BatchNorm2d(planes),
            )

        layers = []
        layers.append(block(self.inplanes, planes, stride, downsample, dilation=previous_dilation))
        self.inplanes = planes
        for _ in range(1, blocks):
            layers.append(block(self.inplanes, planes, dilation=self.dilation))

        return nn.Sequential(*layers)

    def features(self, x):
        x = self.conv1(x)
        x = self.bn1(x)
        if USE_RELU:
            x = self.relu(x)
        x = self.maxpool(x)

        x = self.layer1(x)
        x = self.layer2(x)
        x = self.layer3(x)
        x = self.layer4(x)

        return x

    def forward(self, x):
        x = self.features(x)
        self.feature_maps = [x]
        x = self.avgpool(x)
        x = x.view(x.size(0), -1)
        x = self.fc(x)

        return x


def resnet18(**kwargs):
    """Constructs a ResNet-18 model.
    Args:
        pretrained (bool): If True, returns a model pre-trained on ImageNet
    """
    return ResNet(BasicBlock, [2, 2, 2, 2], **kwargs)
