from my_clip import MyClip, MyClipLoss
import torch
from torch.utils.data import DataLoader, Subset
import torchvision.datasets as dset
from PIL import Image
import requests
import clip


# set seed
torch.manual_seed(42)

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model, preprocess = clip.load("ViT-B/16", device=device)
validation_dataset = dset.CocoCaptions(root = './datasets/mscoco/val2014',
    annFile = 'datasets/mscoco/annotations/captions_val2014.json',
    # transform=[transforms.PILToTensor()])
    transform=preprocess,
    )

clip_model = MyClip().to(device)

'''
Testing on random images and captions
'''

image1 = Image.open(requests.get('https://m.media-amazon.com/images/M/MV5BMTM3OTUwMDYwNl5BMl5BanBnXkFtZTcwNTUyNzc3Nw@@._V1_FMjpg_UX1000_.jpg', stream=True).raw)


captions = ['face of scarlett johansson', 'face of Sophie Turner']

preprocessed_image = preprocess(image1)

preprocessed_image = preprocessed_image.unsqueeze(0).to(device)

outputs = clip_model(preprocessed_image, captions, scale=False) # so that I get cosine similarities directly

logits_per_image, logits_per_text = outputs # shape of both: ([batch_size, batch_size])

print('logits_per_image ', logits_per_image)

exit()

'''
Testing on self made validation set
'''

# validation hypers

validation_hyperparameters = {
    'small_train_loader_batch_size': 64,
    'small_train_loader_dataset_size': 100
}





# just for validation
subset_indices = torch.randint(0, len(validation_dataset) , (validation_hyperparameters['small_train_loader_dataset_size'],))

# get 100 indices that are not in train_data_subset
val_indices = torch.randint(0, len(validation_dataset) , (100,))
i = 0
while i < 100:
    while val_indices[i] in subset_indices:
        val_indices[i] = torch.randint(0, len(validation_dataset) , (1,))
    i += 1
print('i ', i)


def collate_fn(batch):
    '''
    batch is a list of tuples?
    each tuple is of the form (image, caption)
    image is a tensor of shape [3, 224, 224]
    caption is a tuple of strings
    '''

    imgs, og_captions = zip(*batch)

    # keep only first caption for each image
    captions = [caption[0] for caption in og_captions]

    # caption2 = [caption[0] for caption in og_captions]
    # return (caption2, captions)
    return (torch.stack(imgs), captions)



# get 100 images from train_dataset that are not in train_data_subset
val_data_subset = Subset(validation_dataset, val_indices)

val_dataloader = DataLoader(val_data_subset, batch_size=validation_hyperparameters['small_train_loader_batch_size'], shuffle=True, collate_fn=collate_fn, num_workers=0)

# test model with validation set
clip_model.eval()


with torch.no_grad():
    

    for (img, caption) in val_dataloader:
        outputs = clip_model(img, caption, scale=False) # so tha I get cosine similarities directly
        logits_per_image, logits_per_text = outputs # shape of both: ([batch_size, batch_size])

        # print('logits_per_image ', logits_per_image)

        # print logits per image for first 5 images
        # print('logits_per_image ', logits_per_image[:5, :5])
        cosine_similarities = logits_per_image.diag() # shape: [64]
        # get median cosine similarity
        median_cosine_similarity = torch.median(cosine_similarities)
        print('median cosine similarity ', median_cosine_similarity)

        # get median of elements that are not on the diagonal
        non_similar_median_cosine_similarity = logits_per_image[~torch.eye(logits_per_image.shape[0], dtype=bool)].median()
        print('non_similar_median_cosine_similarity ', non_similar_median_cosine_similarity)






