# FlowNet in Tensorflow
# Training
# ==============================================================================

import sys
import argparse
import os
from os.path import dirname

import cv2
import numpy as np
import tensorflow as tf
import tensorflow.contrib.slim as slim
from tensorflow.python.client import timeline
from tensorflow.python.platform import flags
from tensorflow.python.training import saver as tf_saver

import flownet

dir_path = dirname(os.path.realpath(__file__))

# Basic model parameters as external flags.
FLAGS = flags.FLAGS

flags.DEFINE_string('splitlist', 'data/FlyingChairs_release_test_train_split.list',
                           'List where to split train / test')

flags.DEFINE_integer('img_shape', [384, 512, 3],
                           'Image shape: width, height, channels')

flags.DEFINE_integer('flow_shape', [384, 512, 2],
                           'Image shape: width, height, 2')

flags.DEFINE_float('learning_rate', 1e-4,
                           'Initial learning rate')

flags.DEFINE_float('minimum_learning_rate', 1e-6,
                   'Lower bound for learning rate.')

flags.DEFINE_float('decay_factor', 0.33, 
					'Learning rate decay factor.')

flags.DEFINE_float('decay_steps', 100000,
                   'Learning rate decay interval in steps.')

flags.DEFINE_integer('img_summary_num', 2,
                           'Number of images in summary')

flags.DEFINE_integer('max_checkpoints', 5,
                     'Maximum number of recent checkpoints to keep.')

flags.DEFINE_float('keep_checkpoint_every_n_hours', 5.0,
                   'How often checkpoints should be kept.')

flags.DEFINE_integer('save_summaries_secs', 150,
                     'How often should summaries be saved (in seconds).')

flags.DEFINE_integer('save_interval_secs', 300,
                     'How often should checkpoints be saved (in seconds).')

flags.DEFINE_integer('log_every_n_steps', 100,
                     'Logging interval for slim training loop.')

flags.DEFINE_integer('trace_every_n_steps', 1000,
                     'Logging interval for slim training loop.')

flags.DEFINE_integer('max_steps', 500000, 
					'Number of training steps.')

flags.DEFINE_integer('batchsize', 8, 'Batch size.')

def convert_to_tensor(imgs_np, flows_np):
	"""convert numpy to tensor"""
	flows = tf.stack([tf.convert_to_tensor(flows_np[i], dtype = tf.float32) 
  						for i in range(FLAGS.batchsize)])
	imgs_0 = tf.stack([tf.convert_to_tensor(imgs_np[0][i], dtype = tf.float32) 
  						for i in range(FLAGS.batchsize)])
	imgs_1 = tf.stack([tf.convert_to_tensor(imgs_np[1][i], dtype = tf.float32) 
  						for i in range(FLAGS.batchsize)])

  	return imgs_0, imgs_1, flows

def main(_):
	"""Train FlowNet for a FLAGS.max_steps."""

	# Get the lists of two images and the .flo file with a batch reader
	print("--- Start FlowNet Training ---")
	print("--- Create data list for input batch reading ---")
	data_lists = flownet.read_data_lists()
	# we (have) split the Flying Chairs dataset into 22, 232 training and 640 test samples 
	train_set = data_lists.train

	imgs_np, flows_np  = train_set.next_batch(FLAGS.batchsize)
	# Add the variable initializer Op.
	with tf.Graph().as_default():

		# Generate tensors from numpy images and flows.
		imgs_0, imgs_1, flows = convert_to_tensor(imgs_np, flows_np)

		# Image / Flow Summary
		flownet.image_summary(imgs_0, imgs_1, "A", flows)

		# chromatic tranformation in imagess
		chroI_0, chroI_1 = flownet.chromatic_augm(imgs_0, imgs_1)

		#affine tranformation in tf.py_func fo images and flows_pl
		aug_data = [chroI_0, chroI_1, flows]
		augI_0, augI_1, augF = flownet.affine_trafo(aug_data) 

		#rotation / scaling (Cropping) 
		rotI_0, rotI_1, rotF = flownet.rotation(augI_0, augI_1, augF) 

		# Build a Graph that computes predictions from the inference model.
		calc_flows = flownet.inference(rotI_0, rotI_1)

		# Image / Flow Summary
		flownet.image_summary(rotI_0, rotI_1, "E_result", calc_flows)

		# loss
		train_loss = flownet.train_loss(calc_flows, rotF)
		global_step = slim.get_or_create_global_step()

		# Add to the Graph the Ops that calculate and apply gradients.
		train_op = flownet.create_train_op(train_loss, global_step)

		# Create a saver for writing training checkpoints.
		saver = tf_saver.Saver(max_to_keep=FLAGS.max_checkpoints,
						keep_checkpoint_every_n_hours=FLAGS.keep_checkpoint_every_n_hours)

		# Start the training loop.
		print("--- Start the training loop ---")

		slim.learning.train(
			train_op,
			logdir=FLAGS.logdir + '/train',
			save_summaries_secs=FLAGS.save_summaries_secs,
			save_interval_secs=FLAGS.save_interval_secs,
			summary_op=tf.summary.merge_all(),
			log_every_n_steps=FLAGS.log_every_n_steps,
			trace_every_n_steps=FLAGS.trace_every_n_steps,
			saver=saver,
			number_of_steps=FLAGS.max_steps,
		)
		
if __name__ == '__main__':
	parser = argparse.ArgumentParser()
	parser.add_argument(
	  '--datadir',
	  type=str,
	  default='data/FlyingChairs_examples/',
	  help='Directory to put the input data.'
	)
	parser.add_argument(
	  '--logdir',
	  type=str,
	  default='log',
	  help='Directory where to write event logs and checkpoints'
	)
	parser.add_argument(
	  '--imgsummary',
	  type=bool,
	  default=False,
	  help='Make image summary'
	)

	FLAGS.datadir = os.path.join(dir_path,  parser.parse_args().datadir)
	FLAGS.logdir = os.path.join(dir_path, parser.parse_args().logdir)
	FLAGS.imgsummary = parser.parse_args().imgsummary
	tf.app.run()
