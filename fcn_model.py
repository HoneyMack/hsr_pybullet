import torchvision.models as models
from torch import nn
import numpy as np
import torch
import torch.nn.functional as F
import time

#from self_attention import SAModule
#from self_attention import ViT
from self_attention_cv import ViT
from self_attention_cv.transformer_vanilla.mhsa import MultiHeadSelfAttention
from self_attention_cv.transformer_vanilla.transformer_block import TransformerBlock
import resnet


#class MHSAEncoder(nn.Module):
#    def __init__(self, dim, heads, dim_head):

#class MHSAEncoder(nn.Module):
#    def __init__(self, dim, blocks, heads, dim_head):
#        super().__init__()
#        #self.layers = nn.ModuleList([MultiHeadSelfAttention(dim, heads, dim_head) for _ in range(blocks)])
#        self.layers = nn.ModuleList([TransformerBlock(dim, heads, dim_head, dim, 0) for _ in range(blocks)])
#    
#    def forward(self, x, mask):
#        for layer in self.layers:
#            x = layer(x)
#        return x


class FCN(nn.Module):
    def __init__(self, num_rotations=16, use_fc=False, fast=False, debug=False):
        super().__init__()

        self.num_rotations = num_rotations
        self.use_cuda = True
        self.use_fc = use_fc
        self.debug = debug
        self.fast = fast

        #modules = list(models.resnet18().children())[:-5]
        #self.backbone = nn.Sequential(*modules)
        self.resnet = resnet.resnet18(num_input_channels=1)#models.resnet18()
        #backbone = resnet.resnet18(num_input_channels=3, num_classes=1)
        #self.resnet.cuda()
        #self.backbone = backbone.features
        
        def decoder(n, out):
          return nn.Sequential(
            nn.Conv2d(n, 128, 1, 1),
            nn.BatchNorm2d(128),
            nn.ReLU(),
            nn.UpsamplingBilinear2d(scale_factor=2),
            nn.Conv2d(128, 32, 1, 1),
            nn.BatchNorm2d(32),
            nn.ReLU(),
            nn.UpsamplingBilinear2d(scale_factor=2),
            nn.Conv2d(32, out, 1, 1),
          )
        self.end = decoder(512, num_rotations if fast else 1)

        D = 64
        #self.tf = MHSAEncoder(dim=D, blocks=2, heads=H, dim_head=D // H)
        self.vit = ViT(img_dim=56, in_channels=512, patch_dim=4, heads=4, blocks=2, dim_linear_block=D, dim=D, dropout=0, classification=False)
        #self.gg = nn.Conv2d(514, 512, 1, 1) 
        #self.s2d = nn.Softmax2d()
        #self.p_decoder = decoder(1)
        #self.p_resnet = resnet.resnet18(num_input_channels=1)
        #self.fc_cnn = nn.Sequential(
        #    nn.Conv2d(64, 512, 1, 1),
        #    #nn.BatchNorm2d(1),
        #    #nn.ReLU(),
        #)
        self.dconv = nn.Sequential(
            #nn.Conv2d(D, 512, 4, 4),
            #nn.BatchNorm2d(512),
            #nn.ReLU(),
            nn.ConvTranspose2d(D, 512, 4, stride=4),
            nn.BatchNorm2d(512),
            nn.ReLU(),
        )
        #self.fc = nn.Sequential(
        #    ##nn.Dropout(),
        #    nn.Linear(28*28, 28*28),
        #    nn.ReLU(),
        #    nn.Linear(28*28, 28*28),
        #    #nn.BatchNorm1d(56*56),
        #    nn.ReLU(),
        #    #nn.Identity()
        #    ##nn.Dropout()
        #)
        
        #self.up = nn.Sequential(
        #    nn.Conv2d(1, 1, 1, 1),
        #    nn.UpsamplingBilinear2d(scale_factor=8),
        #)
        #self.up = decoder(513, 1)
        #self.vit = ViT(img_dim=224, in_channels=3, patch_dim=16,
                #dim=64,
                #blocks=2,
                #heads=1,
                #dim_linear_block=64,
        #        classification=False)
        #self.vit_fc = nn.Linear(512, 64)
        #self.vit_upsample = nn.Sequential(
        #    nn.Conv2d(512, 256, 1, 1),
        #    nn.BatchNorm2d(256),
        #    nn.ReLU(),
        #    nn.UpsamplingBilinear2d(scale_factor=4),
        #    nn.Conv2d(256, 128, 1, 1),
        #    nn.BatchNorm2d(128),
        #    nn.ReLU(),
            #nn.BatchNorm2d(64),
            #nn.UpsamplingBilinear2d(scale_factor=2),
            #nn.Conv2d(512, 514, 1, 1),
        #)

    def backbone(self, x):
        x = self.resnet.features(x)

        return x

    def cat_grid(self, input, affine_grid=None):
        x = torch.abs(torch.linspace(-0.5, 0.5, steps=input.shape[-2])).cuda() # side
        y = torch.tensor(torch.linspace(0, 1, steps=input.shape[-1])).cuda()  # forward
        grid_x, grid_y = torch.meshgrid(x, y)
        grid_x = grid_x.unsqueeze(0).unsqueeze(0)
        grid_y = grid_y.unsqueeze(0).unsqueeze(0)
        grid_x = grid_x.repeat(len(input), 1, 1, 1)
        grid_y = grid_y.repeat(len(input), 1, 1, 1)
        grid = torch.cat([grid_x, grid_y], 1)

        if affine_grid is not None:
            flow_grid = F.affine_grid(affine_grid, input.size())
            grid = F.grid_sample(grid, flow_grid, mode='nearest')

        x = torch.cat([input, grid], 1)

        return x

    def self_attention(self, x):
        z = self.vit(x)
        #z = self.vit_fc(z)
        z = z.reshape(-1, 14, 14, z.size(2))
        z = z.permute(0, 3, 1, 2)
        z = self.dconv(z)
        #z = F.interpolate(z, (56, 56), mode='bilinear')
        #x = F.relu(z)#x + z)
        return z

    def forward(self, x):
        bs = len(x)
        # y = self.end(self.backbone(x))

        # assert x.shape[-2:] == y.shape[-2:], 'input =/= output shape {} {}'.format(x.shape, y.shape)
        output_prob = []

        # x = x[:, 0:1]
        # x = self.cat_meshgrid(x)

        #vit_h = self.self_attention(x)

        #if self.use_fc:
        #    p = self.p_resnet.features(x)
        #    #p = self.fc_cnn(p)
        #    s = p[:, 0]
        #    s = F.max_pool2d(s, 2)
        #    s = s.view(-1, 28*28)
        #    s = self.fc(s)
        #    s = s.view(-1, 1, 28, 28)
        #    #s = F.interpolate(s, (56, 56))
        #    #p = self.up(torch.cat([p, s], 1))
        #    p = self.up(s)

        if self.num_rotations == 1 or self.fast:
            # h = self.backbone(x)
            #if self.use_fc:
            #    a = self.fc(h[:, 0].view(-1, 56*56)).view(-1, 1, 56, 56)
            #    h = torch.cat([h, a], 1)
            if self.use_fc:
                h = self.backbone(x)
                h = h + self.self_attention(h)
                #p = self.s2d(self.gg(g))
                #h = p
                #out = self.dconv(h)
                out = self.end(h)
            else:
                h = self.backbone(x)

                out = self.end(h)#vit_h)
            #a = self.up(a)
            #out = out * a
            #if self.use_fc:
            #    out = torch.minimum(g, p)
            #else:
            #    out = g
            g = out
            
            if self.debug:
                if self.use_fc:
                    return out, g, g
                else:
                    return out, g, g

            return out
        else:
            for rotate_idx in range(self.num_rotations):
                rotate_theta = np.radians(rotate_idx * (360 / self.num_rotations))

                # Compute sample grid for rotation BEFORE neural network
                affine_mat_before = np.asarray(
                    [[np.cos(-rotate_theta), np.sin(-rotate_theta), 0], [-np.sin(-rotate_theta), np.cos(-rotate_theta), 0]])
                affine_mat_before.shape = (2, 3, 1)
                affine_mat_before = torch.from_numpy(affine_mat_before).permute(2, 0, 1).float()
                affine_mat_before = affine_mat_before.repeat(bs, 1, 1)

                #print(affine_mat_before.shape, x.shape)
                #print(affine_mat_before.is_cuda, x.is_cuda)

                if self.use_cuda:
                    affine_mat_before = affine_mat_before.cuda()
                    flow_grid_before = F.affine_grid(affine_mat_before, x.size())
                    #flow_grid_vit = F.affine_grid(affine_mat_before, vit_h.size())
                else:
                    affine_mat_before = affine_mat_before.detach()
                    flow_grid_before = F.affine_grid(affine_mat_before, x.size())

                # Rotate images clockwise
                if self.use_cuda:
                    rotate_depth = F.grid_sample(x.detach().cuda(), flow_grid_before, mode='nearest')
                    #rotate_vit_h = F.grid_sample(vit_h, flow_grid_vit, mode='nearest')
                else:
                    rotate_depth = F.grid_sample(x.detach(), flow_grid_before, mode='nearest')

                # Compute intermediate features
                #output_map = self.end(torch.cat([rotate_vit_h, self.backbone(rotate_depth)], 1))
                h = self.backbone(rotate_depth)
                #if self.use_fc:
                #    a = self.fc(h[:, 0].view(-1, 56*56)).view(-1, 1, 56, 56)
                #    h = torch.cat([h, a], 1)
                output_map = self.end(h)

                # Compute sample grid for rotation AFTER branches
                affine_mat_after = np.asarray(
                    [[np.cos(rotate_theta), np.sin(rotate_theta), 0], [-np.sin(rotate_theta), np.cos(rotate_theta), 0]])
                affine_mat_after.shape = (2, 3, 1)
                affine_mat_after = torch.from_numpy(affine_mat_after).permute(2, 0, 1).float()
                affine_mat_after = affine_mat_after.repeat(bs, 1, 1)

                if self.use_cuda:
                    flow_grid_after = F.affine_grid(affine_mat_after.detach().cuda(),
                                                    output_map.size())
                else:
                    flow_grid_after = F.affine_grid(affine_mat_after.detach(),
                                                    output_map.size())

                # Forward pass through branches, undo rotation on output predictions, upsample results
                h = F.grid_sample(output_map, flow_grid_after, mode='nearest')
                if self.use_fc:
                    h = torch.minimum(p, h)
                output_prob.append(h)

        out = torch.stack(output_prob)  # R x N x 1 x H x W
        out = out.squeeze(2)  # R x N x H x W
        out = out.permute(1, 0, 2, 3)

        if self.debug:
            return out, p

        return out


if __name__ == '__main__':
    model = FCN()
    model.cuda()
    model.eval()

    while True:
        y = model(torch.rand((1, 3, 224, 224)).cuda())
        print(torch.stack(y).shape)
