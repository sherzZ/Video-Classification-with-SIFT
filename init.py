import cv2
from sklearn.model_selection import train_test_split
import os
import skvideo.io
import numpy as np
from scipy.spatial import KDTree
from sklearn.svm import LinearSVC
from sklearn.metrics import accuracy_score, precision_score, recall_score
from sklearn.utils import shuffle
import argparse

sift = cv2.xfeatures2d.SIFT_create()


def get_x_y(path, positive_class):

    x = []
    y = []
    for folder in os.listdir(path):
        if folder == '.DS_Store': # ignore autogenerated file on macs
            continue
        for file in os.listdir(os.path.join(path, folder)):
            if file =='.DS_Store': # ignore autogenerated file on macs
                continue
            x.append(os.path.join(path, folder, file))
            y.append(folder == positive_class)

    return x, y


def compute_sift(image):

    gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
    kp, des = sift.detectAndCompute(gray, None)  # keypoints, descriptors
    return des


def create_bow(x_features, dictionary, method, save_path):

    kdtree = KDTree(dictionary)
    bins = dictionary.shape[0]

    print('calculating BoW...')
    list_videos_hist = []
    for i, video in enumerate(x_features):
        print()
        print('video', i + 1, 'out of', len(x_features))
        video_hist = []
        for j, frame in enumerate(video):
            print('Frame', j + 1, 'out of', len(video))
            dis, indices = kdtree.query(frame)
            hist, _ = np.histogram(indices, bins=bins)
            hist = hist / len(indices) #normalizes

            video_hist.append(hist)

        video_hist = np.array(video_hist)

        if method == 'mean':
            video_hist = np.mean(video_hist, 0)
        elif method == 'max':
            video_hist = np.amax(video_hist, 0)
        else:
            raise Exception('Method not found')

        list_videos_hist.append(video_hist)

    np.save(save_path, np.array(list_videos_hist))

    return np.array(list_videos_hist)


def get_video_train_test(x, y, save_path):
    x, y = shuffle(x, y, random_state=42)
    x_train, x_test, y_train, y_test = train_test_split(x, y)

    np.save(os.path.join(save_path, 'xtrainfiles'), x_train)
    np.save(os.path.join(save_path, 'xtestfiles'), x_test)
    np.save(os.path.join(save_path, 'ytrain.npy'), y_train)
    np.save(os.path.join(save_path, 'ytest.npy'), y_test)

    return x_train, x_test, y_train, y_test


def create_features(x):

    features = []

    for i, video in enumerate(x):

        print('video', i + 1, 'out of', len(x))

        videogen = skvideo.io.vreader(video)
        video_frames = []  # all frames for the current video

        for frame in videogen:
            des = compute_sift(frame)
            if des is not None:
                video_frames.append(des)

        features.append(video_frames)

        print()
        print('success', video)
        print()

    return features


def create_dictionary(x_train_features):

    print('Creating dictionary...')

    dictionary_size = 20
    bow = cv2.BOWKMeansTrainer(dictionary_size)

    # for every training video add every frame to the bow

    for i, video in enumerate(x_train_features):
        print('video', i + 1, 'out of', len(x_train_features))
        num_frames = len(video)
        random_perm = np.random.permutation(num_frames)
        for i in random_perm[:5]:
            frame = video[i]
            bow.add(frame)

    dictionary = bow.cluster()  # compute centroids

    return dictionary


def load_train_test(save_path):

    x_train = np.load(os.path.join(save_path, 'xtrainfiles.npy'))
    x_test = np.load(os.path.join(save_path, 'xtestfiles.npy'))
    y_train = np.load(os.path.join(save_path, 'ytrain.npy'))
    y_test = np.load(os.path.join(save_path, 'ytest.npy'))

    return x_train, x_test, y_train, y_test


def run_from_train_test(root_path, method):
    save_path = os.path.join(root_path, 'generated')
    method_path = os.path.join(save_path, method)
    x_train, x_test, y_train, y_test = load_train_test(save_path)
    _run_from_train_test(x_train, x_test, y_train, y_test, method, method_path)


def _run_from_train_test(x_train, x_test, y_train, y_test, method, method_path):

    x_train_features = create_features(x_train)
    x_test_features = create_features(x_test)

    dictionary = create_dictionary(x_train_features)

    x_train_bow = create_bow(x_train_features, dictionary, method, os.path.join(method_path, 'xtrainbow.npy'))
    x_test_bow = create_bow(x_test_features, dictionary, method, os.path.join(method_path, 'xtestbow.npy'))

    predict(x_train_bow, x_test_bow, y_train, y_test)


def run_all(root_path, positive_class_name, method):

    save_path = os.path.join(root_path, 'generated')
    method_path = os.path.join(save_path, method)
    movies_path = os.path.join(root_path, 'movies')
    os.makedirs(method_path, exist_ok=True)

    x, y = get_x_y(movies_path, positive_class_name)

    x_train, x_test, y_train, y_test = get_video_train_test(x, y, save_path)

    _run_from_train_test(x_train, x_test, y_train, y_test, method, method_path)


def predict(x_train, x_test, y_train, y_test):

    model = LinearSVC()
    model.fit(x_train, y_train)
    predictions = model.predict(x_test)
    acc = accuracy_score(y_test, predictions)
    precision = precision_score(y_test, predictions)
    recall = recall_score(y_test, predictions)
    print('Accuracy:', acc, 'Recall:', recall, 'Precision:', precision)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Learning Curve Analysis Research')
    parser.add_argument('-r', '--root_folder', help='Root folder', required=True)
    parser.add_argument('-m', '--method', help='Method', required=True)

    args = parser.parse_args()
    run_from_train_test(args.root_folder, args.method)