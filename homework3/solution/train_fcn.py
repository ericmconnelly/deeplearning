import torch
import numpy as np

from .models import FCN, save_model
from .utils import load_dense_data, DENSE_CLASS_DISTRIBUTION, ConfusionMatrix
from . import dense_transforms
import torch.utils.tensorboard as tb


def train(args):
    from os import path
    model = FCN()
    train_logger, valid_logger = None, None
    if args.log_dir is not None:
        train_logger = tb.SummaryWriter(path.join(args.log_dir, 'train'), flush_secs=1)
        valid_logger = tb.SummaryWriter(path.join(args.log_dir, 'valid'), flush_secs=1)

    """
    Your code here, modify your HW1 / HW2 code

    """
    import torch

    device = torch.device('cuda') if torch.cuda.is_available() else torch.device('cpu')

    model = FCN().to(device)
    if args.continue_training:
        model.load_state_dict(torch.load(path.join(path.dirname(path.abspath(__file__)), 'fcn.th')))

    # optimizer = torch.optim.SGD(model.parameters(), lr=args.learning_rate, momentum=0.9, weight_decay=1e-3)
    optimizer = torch.optim.Adam(model.parameters(), lr=args.learning_rate, weight_decay=1e-5)
    w = torch.as_tensor(DENSE_CLASS_DISTRIBUTION)**(-args.gamma)
    loss = torch.nn.CrossEntropyLoss(weight=w / w.mean()).to(device)

    import inspect
    transform = eval(args.transform, {k: v for k, v in inspect.getmembers(dense_transforms) if inspect.isclass(v)})
    train_data = load_dense_data('dense_data/train', num_workers=4, transform=transform)
    valid_data = load_dense_data('dense_data/valid', num_workers=4)

    global_step = 0
    for epoch in range(args.num_epoch):
        model.train()
        conf = ConfusionMatrix()
        for img, label in train_data:
            img, label = img.to(device), label.to(device).long()

            logit = model(img)
            loss_val = loss(logit, label)
            if train_logger is not None and global_step % 100 == 0:
                train_logger.add_image('image', img[0], global_step)
                train_logger.add_image('label', np.array(dense_transforms.label_to_pil_image(label[0].cpu()).
                                                         convert('RGB')), global_step, dataformats='HWC')
                train_logger.add_image('prediction', np.array(dense_transforms.
                                                              label_to_pil_image(logit[0].argmax(dim=0).cpu()).
                                                              convert('RGB')), global_step, dataformats='HWC')

            if train_logger is not None:
                train_logger.add_scalar('loss', loss_val, global_step)
            conf.add(logit.argmax(1), label)

            optimizer.zero_grad()
            loss_val.backward()
            optimizer.step()
            global_step += 1

        if train_logger:
            train_logger.add_scalar('global_accuracy', conf.global_accuracy, global_step)
            train_logger.add_scalar('average_accuracy', conf.average_accuracy, global_step)
            train_logger.add_scalar('iou', conf.iou, global_step)

        model.eval()
        val_conf = ConfusionMatrix()
        for img, label in valid_data:
            img, label = img.to(device), label.to(device).long()
            logit = model(img)
            val_conf.add(logit.argmax(1), label)

        if valid_logger is not None:
            valid_logger.add_image('image', img[0], global_step)
            valid_logger.add_image('label', np.array(dense_transforms.label_to_pil_image(label[0].cpu()).
                                                     convert('RGB')), global_step, dataformats='HWC')
            valid_logger.add_image('prediction', np.array(dense_transforms.
                                                          label_to_pil_image(logit[0].argmax(dim=0).cpu()).
                                                          convert('RGB')), global_step, dataformats='HWC')

        if valid_logger:
            valid_logger.add_scalar('global_accuracy', val_conf.global_accuracy, global_step)
            valid_logger.add_scalar('average_accuracy', val_conf.average_accuracy, global_step)
            valid_logger.add_scalar('iou', val_conf.iou, global_step)

        if valid_logger is None or train_logger is None:
            print('epoch %-3d \t acc = %0.3f \t val acc = %0.3f \t iou = %0.3f \t val iou = %0.3f' %
                  (epoch, conf.global_accuracy, val_conf.global_accuracy, conf.iou, val_conf.iou))
        save_model(model)


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser()

    parser.add_argument('--log_dir')
    # Put custom arguments here
    parser.add_argument('-n', '--num_epoch', type=int, default=50)
    parser.add_argument('-lr', '--learning_rate', type=float, default=1e-3)
    parser.add_argument('-g', '--gamma', type=float, default=0, help="class dependent weight for cross entropy")
    parser.add_argument('-c', '--continue_training', action='store_true')
    parser.add_argument('-t', '--transform',
                        default='Compose([ColorJitter(0.9, 0.9, 0.9, 0.1), RandomHorizontalFlip(), ToTensor()])')

    args = parser.parse_args()
    train(args)
