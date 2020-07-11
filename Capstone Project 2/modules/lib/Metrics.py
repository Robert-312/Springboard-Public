import numpy as np
import pandas as pd
from sklearn import metrics
import matplotlib.pyplot as plt

from enum import Enum

import torch
import torch.utils.data

class MetricDataSource(Enum):
    Both = 0
    TrainingOnly = 1
    ValidationOnly = 2

class Metrics():
    
    """
    docstring
    """
    
    def __init__(self, target_columns, train_actual, val_actual, cc=10, scc=5):
        self.target_columns = target_columns
        self.train_actual = train_actual
        self.val_actual = val_actual
        
        self.cc = cc
        self.scc = scc
        
        self.train_prediction_hx = {}
        self.train_probability_hx = {}

        self.val_prediction_hx = {}
        self.val_probability_hx = {}

        self.epoch_train_predictions = {}
        self.df_train_prediction = None
        
        self.epoch_train_probabilities = {}
        self.df_train_probability = None

        self.epoch_val_predictions = {}
        self.df_val_prediction = None
        
        self.epoch_val_probabilities = {}
        self.df_val_probability = None
        
        
        
 # DATA
        
    def getPredictionsFromOutput(self, outputs):
        """
        We are using BCEWithLogitsLoss for out loss
        In this loss funciton, each label gets the sigmoid (inverse of Logit) before the CE loss
        So our model outputs the raw values on the last FC layer
        This means we have to apply sigmoid to our outputs to squash them between 0 and 1
        We then take values >= .5 as Positive and < .5 as Negative 
        """

        probabilities = torch.sigmoid(outputs.data) 
        predictions = probabilities.clone()
        predictions[predictions >= 0.5] = 1 # assign 1 label to those with less than 0.5
        predictions[predictions < 0.5] = 0 # assign 0 label to those with less than 0.5   
        return probabilities, predictions   
            
    def updateProbabilities(self, dictionary, ids, probabilities):
        """
        Our model outputs are raw scores.
        We want to be able to build ROC curves for some or all of our targets
        For the ROC curve, we need the actuals for each label along with the probability of the prediction.
        So like the predicitons, we want to keep track of the probabilities
        """
        for i in range(len(ids)):
            id = ids[i].item()    
            dictionary[id] = [float(f.item()) for f in probabilities[i]]     
    
    def updatePredictions(self, dictionary, ids, predictions):
        """
        Keep track of predictions using the same index as our DataFrame
        This will allow us to compare to the actual labels

        We only are taking the last prediction for each x-ray, but we could extend this later if wanted.
        """

        for i in range(len(ids)):
            id = ids[i].item()    
            dictionary[id] = [int(f.item()) for f in predictions[i]]          
            
    def appendEpochBatchData(self, ids, outputs, is_validation=False):
        """
        docstring
        """
        
        probabilities, predictions = self.getPredictionsFromOutput(outputs)        

        if is_validation:
            self.updateProbabilities(self.epoch_val_probabilities, ids, probabilities)
            self.updatePredictions(self.epoch_val_predictions, ids, predictions)
        else:
            self.updateProbabilities(self.epoch_train_probabilities, ids, probabilities)
            self.updatePredictions(self.epoch_train_predictions, ids, predictions)    
            
    def getPredictionDataFrame(self, epoch_predictions):
        result = pd.DataFrame(epoch_predictions).transpose()
        result.columns = self.target_columns
        return result

    def getProbilityDataFrame(self, epoch_probabilities):
        result = pd.DataFrame(epoch_probabilities).transpose()
        result.columns = self.target_columns
        return result
        
    def closeEpoch(self, epochNumber, is_validation=False):
        """
        docstring
        """
        
        if is_validation:
            self.df_val_prediction = self.getPredictionDataFrame(self.epoch_val_predictions)
            self.val_prediction_hx[epochNumber] = self.df_val_prediction
            self.epoch_val_predictions = {}

            self.df_val_probability = self.getProbilityDataFrame(self.epoch_val_probabilities)
            self.val_probability_hx[epochNumber] = self.df_val_probability
            self.epoch_val_probabilities = {}
        else:
            self.df_train_prediction = self.getPredictionDataFrame(self.epoch_train_predictions)
            self.train_prediction_hx[epochNumber] = self.df_train_prediction
            self.epoch_train_predictions = {}

            self.df_train_probability = self.getProbilityDataFrame(self.epoch_train_probabilities)
            self.train_probability_hx[epochNumber] = self.df_train_probability
            self.epoch_train_probabilities = {}
        
# DISPLAY        
        
    def displayCombinedMetrics(self, y_true, y_pred, average):
        """
        docstring
        """
        

        accuracy_score = metrics.accuracy_score(y_true=y_true, y_pred=y_pred, normalize=True)
        hamming_loss = metrics.hamming_loss(y_true=y_true, y_pred=y_pred)
        recall_score = metrics.recall_score(y_true=y_true, y_pred=y_pred, average=average, zero_division=0)
        precision_score = metrics.precision_score(y_true=y_true, y_pred=y_pred, average=average, zero_division=0)
        f1_score = metrics.f1_score(y_true=y_true, y_pred=y_pred, average=average, zero_division=0)


        df_combined = pd.DataFrame({
                                    'Accuracy Score':[accuracy_score],
                                    'Hamming Loss':[hamming_loss],
                                    'Combined Recall':[recall_score],
                                    'Combined Precision':[precision_score],
                                    'Combined F1':[f1_score]})

        df_combined = df_combined.transpose()
        df_combined.columns = ['Score for all Targets']

        display(df_combined) 
        
    def displayMetricDataFrame(self, y_true, y_pred, y_prob, include_targets=None):
        """
        docstring
        """
        
        target_columns = self.target_columns

        if include_targets is None:
            include_targets = target_columns

        true_positive_count = y_true.sum(axis=0)

        nans = np.ones(len(target_columns))
        nans[:] = np.nan
        errors = {}

        try:
            itemized_recall = metrics.recall_score(y_true=y_true, y_pred=y_pred, average=None)
        except Exception as e:
            errors['Recall'] = e
            itemized_recall = nans


        try:    
            itemized_precision = metrics.precision_score(y_true=y_true, y_pred=y_pred, average=None)
        except Exception as e:
            errors['Precision'] = e
            itemized_precision = nans

        try:    
            itemized_f1 = metrics.f1_score(y_true=y_true, y_pred=y_pred, average=None)
        except Exception as e:
            errors['F1'] = e
            itemized_f1 = nans

        try:    
            itemized_auc = metrics.roc_auc_score(y_true=y_true, y_score=y_prob, average=None)
        except Exception as e:
            errors['ROC AUC'] = e
            itemized_auc = nans

        try:    
            itemized_ap = metrics.average_precision_score(y_true=y_true, y_score=y_prob, average=None)
        except Exception as e:
            errors['Avg Precision'] = e
            itemized_auc = nans

            ap = metrics.average_precision_score(target_true, target_probs)

        df_itemized = pd.DataFrame({'Target':target_columns, 
                                    'True Positive Count':true_positive_count, 
                                    'Recall':itemized_recall, 
                                    'Precision':itemized_precision, 
                                    'F1':itemized_f1, 
                                    'ROC AUC':itemized_auc, 
                                    'Avg Precision':itemized_ap})

        df_itemized = df_itemized[df_itemized.Target.isin(include_targets)]

        display(df_itemized)

        if len(errors) > 0:
            print(errors)
            
    def plotROC(self, target_columns, Y_true, Y_prob, include_targets=None, cols=2, height=4, width=14):
        """
        docstring
        """
        
        if include_targets is None:
            include_targets = target_columns

        subplot_count = len(include_targets)
        plt_cols = cols
        plt_rows = int(np.ceil(subplot_count / plt_cols))
        figure_height = plt_rows * height
        f = plt.figure(figsize=(width, figure_height))
        gs = f.add_gridspec(plt_rows, plt_cols)
        current_plot = 0

        # Build ROC curves one label at a time
        for i in range(len(target_columns)):
            target_name = target_columns[i]

            if target_name in include_targets:
                target_true = Y_true[:,i]
                target_probs = Y_prob[:,i]

                fpr, tpr, threshold = metrics.roc_curve(target_true, target_probs)
                roc_auc = metrics.auc(fpr, tpr)

                ax = f.add_subplot(gs[current_plot])
                ax.set_title(target_name + ' - ROC')
                ax.plot(fpr, tpr, 'b', label = 'AUC = %0.2f' % roc_auc)
                ax.legend(loc = 'lower right')
                ax.plot([0, 1], [0, 1],'r--')
                ax.set_xlim([0, 1])
                ax.set_ylim([0, 1])
                ax.set_xlabel('False Positive Rate')
                ax.set_ylabel('True Positive Rate')

                current_plot+=1

        f.tight_layout()
        plt.show()             
            
    def plotPrecisionRecall(self, target_columns, Y_true, Y_prob, include_targets=None, cols=2, height=4, width=14):
        """
        docstring
        """
        
        if include_targets is None:
            include_targets = target_columns

        subplot_count = len(include_targets)
        plt_cols = cols
        plt_rows = int(np.ceil(subplot_count / plt_cols))
        figure_height = plt_rows * height
        f = plt.figure(figsize=(width, figure_height))
        gs = f.add_gridspec(plt_rows, plt_cols)
        current_plot = 0

        # Build ROC curves one label at a time
        for i in range(len(target_columns)):
            target_name = target_columns[i]

            if target_name in include_targets:
                target_true = Y_true[:,i]
                target_probs = Y_prob[:,i]

                precision, recall, threshold = metrics.precision_recall_curve(target_true, target_probs)
                ap = metrics.average_precision_score(target_true, target_probs)

                ax = f.add_subplot(gs[current_plot])
                ax.set_title(target_name + ' - Precision/Recall')
                ax.plot(recall, precision, 'b', label = 'AP = %0.2f' % ap)
                ax.legend(loc = 'lower left')
                ax.set_xlim([0, 1])
                ax.set_ylim([0, 1])
                ax.set_xlabel('Recall')
                ax.set_ylabel('Precision')

                current_plot+=1

        f.tight_layout()
        plt.show()             
            
    def displayMetrics(self, metricDataSource = MetricDataSource.Both,
                       showCombinedMetrics=True,
                       showMetricDataFrame=True,
                       showROCCurves=True,
                       showPrecisionRecallCurves=True,
                       include_targets=None,
                       combinedAverageMethod='samples',
                       gridSpecColumnCount=4,
                       gridSpecHeight=3,
                       gridSpecWidth=20):
        """
        docstring
        """
        

        target_columns = self.target_columns
        train_actual = self.train_actual
        val_actual = self.val_actual

        df_train_prediction = self.df_train_prediction
        df_train_probability = self.df_train_probability

        df_val_prediction = self.df_val_prediction
        df_val_probability = self.df_val_probability

        y_train_true = None
        y_train_pred = None
        y_train_prob = None

        y_val_true = None
        y_val_pred = None
        y_val_prob = None

        cc = self.cc # repeat character count
        scc = self.scc # short repeat character count

        if metricDataSource != MetricDataSource.ValidationOnly:
            print('=' * cc + '\nTRAINING\n' + '=' * cc)
            y_train_true = train_actual[target_columns].to_numpy()
            y_train_pred = df_train_prediction.to_numpy()
            y_train_prob = df_train_probability.to_numpy()

            if showCombinedMetrics:
                self.displayCombinedMetrics(y_train_true, y_train_pred, average=combinedAverageMethod)

            if showMetricDataFrame:
                self.displayMetricDataFrame(y_train_true, y_train_pred, y_train_prob, include_targets=include_targets)

            if showROCCurves:
                print('*' * scc + ' ROC ' + '*' * scc)
                self.plotROC(target_columns, y_train_true, y_train_prob, include_targets=include_targets,
                        cols=gridSpecColumnCount, height=gridSpecHeight, width=gridSpecWidth)

            if showPrecisionRecallCurves:
                print('*' * scc + ' Precision / Recall ' + '*' * scc)
                self.plotPrecisionRecall(target_columns, y_train_true, y_train_prob, include_targets=include_targets, 
                        cols=gridSpecColumnCount, height=gridSpecHeight, width=gridSpecWidth)

        if metricDataSource != MetricDataSource.TrainingOnly:
            print('=' * cc + '\nVALIDATION\n' + '=' * cc)
            y_val_true = val_actual[target_columns].to_numpy()
            y_val_pred = df_val_prediction.to_numpy()
            y_val_prob = df_val_probability.to_numpy()

            if showCombinedMetrics:
                self.displayCombinedMetrics(y_val_true, y_val_pred, average=combinedAverageMethod)

            if showMetricDataFrame:
                self.displayMetricDataFrame(y_val_true, y_val_pred, y_val_prob, include_targets=include_targets)

            if showROCCurves:
                print('*' * scc + ' ROC ' + '*' * scc)
                self.plotROC(target_columns, y_val_true, y_val_prob, include_targets=include_targets, 
                        cols=gridSpecColumnCount, height=gridSpecHeight, width=gridSpecWidth)

            if showPrecisionRecallCurves:
                print('*' * scc + ' Precision / Recall ' + '*' * scc)
                self.plotPrecisionRecall(target_columns, y_val_true, y_val_prob, include_targets=include_targets,
                        cols=gridSpecColumnCount, height=gridSpecHeight, width=gridSpecWidth)            