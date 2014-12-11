import pandas as pd
import numpy as np
import scipy as sp

import Statistics as st
import TextProcessing as txtpr
import DataSets as ds
import FeatureGeneration as fg
import DataLoading as dl
import cleanResultantMerge as crm

from sklearn.naive_bayes import MultinomialNB
from sklearn.linear_model import LogisticRegression
from sklearn.linear_model import SGDClassifier
from sklearn import svm
from sklearn.cross_validation import train_test_split
from sklearn.metrics import roc_curve, auc
from sklearn.preprocessing import normalize


# LOAD DATA
essaywords = ds.pickleLoad('EssayWords')
essayvect = ds.pickleLoad('BalancedFull_Essay_Vectorized')
#needwords = ds.pickleLoad('EssayWords')
#needvect = ds.pickleLoad('BalancedFull_Essay_Vectorized')
df = ds.pickleLoad('BalancedFull')

# FEATURE SET 1
denseheaders,densefeatures = fg.getEssayFeatures(df)
densefeatures[np.isnan(densefeatures)]=0

# FEATURE SET 2
df2 = fg.missingFieldIndicator(df)
df2 = fg.dropFeatures(df2)
df2 = fg.createDummies(df2)
df2 = fg.replaceNansWithMean(df2)

# ENTIRE DENSE FEATURE SET
densefeatures2 = np.hstack((densefeatures,df2))
dense_df_headers = denseheaders+list(df2.columns)
dense_df = pd.DataFrame(densefeatures2,columns = dense_df_headers)
rejected = dense_df.pop('rejected')

# GET SUMMARY STATS
summary = crm.getSummary(dense_df,rejected)
dense_df = dense_df.loc[:,summary.distinct_count>1] #remove cols with only 1 distinct value
summary = crm.getSummary(dense_df,rejected)
summary = summary[summary.index != 'rejected']

# NORMALIZE
binary_col_selector = summary.distinct_count == 2
nonbinary_col_selector = summary.distinct_count > 2
binary_cols = dense_df.loc[:,binary_col_selector]
nonbinary_cols = dense_df.loc[:,nonbinary_col_selector]
normalized = pd.DataFrame(normalize(nonbinary_cols,norm='l1'),columns=nonbinary_cols.columns)
dense_normalized = pd.concat((binary_cols,normalized),axis=1,ignore_index=True)

# SELECT SPARSE FEATURES
sparsefeatures = [essayvect]
sparseheaders = sorted(essaywords.vocabulary_.keys(),key=lambda key: essaywords.vocabulary_[key])

# COMBINE ALL FEATURES
features = fg.CombineFeatures([dense_normalized],sparsefeatures)
features = sp.sparse.csr_matrix(features) #required for efficient slicing

# GET NUM DENSE & SPARSE (USED LATER IN COEF)
numdense = dense_normalized.shape[1]
numsparse = sparsefeatures[0].shape[1]
numfeatures = numdense+numsparse

selector_dense = np.arange(numfeatures) < numdense
selector_sparse = selector_dense == False

# TRAIN/TEST SLICING
sel_bool_train = df.train == 1
sel_bool_test = df.train == 0
sel_ind_train = np.where(sel_bool_train)[0]
sel_ind_test = np.where(sel_bool_test)[0]

f_train = features[sel_ind_train]
f_test = features[sel_ind_test]

y_train = np.array(df.rejected[sel_bool_train]).astype(int)
y_test = np.array(df.rejected[sel_bool_test]).astype(int)

# CLASSIFIERS
clf1 = MultinomialNB().fit(f_train, y_train)
probs = clf1.predict_proba(f_test)
fpr,tpr,_ = roc_curve(y_true=y_test,y_score=probs[:,1])
roc_auc = auc(fpr,tpr)
st.plotROC(fpr,tpr,roc_auc,"MultinomialNB")

clf2 = LogisticRegression(penalty='l1').fit(f_train, y_train)
probs = clf2.predict_proba(f_test)
fpr,tpr,_ = roc_curve(y_true=y_test,y_score=probs[:,1])
roc_auc = auc(fpr,tpr)
st.plotROC(fpr,tpr,roc_auc,"LogReg")

clf3 = SGDClassifier(penalty='l1').fit(f_train, y_train)
probs = clf3.decision_function(f_test)
fpr,tpr,_ = roc_curve(y_true=y_test,y_score=probs)
roc_auc = auc(fpr,tpr)
st.plotROC(fpr,tpr,roc_auc,"LogRegSGD")


def coef_dataframe(coef_array,indices,summary=[]):
    df = pd.DataFrame(
                np.vstack((coef_array,np.abs(coef_array))).T,
                index=indices,
                columns=['coef','coef_abs'])
    if len(summary) > 0:
        df = pd.concat((df,summary.loc[indices]),axis=1)
    df = df.sort(['coef_abs'],ascending=False)
    df = df.loc[:,df.columns != 'coef_abs']
    return df

coef_dense = clf2.coef_[0][selector_dense]
coef_binary = coef_dataframe(
                    coef_dense[np.array(binary_col_selector)],
                    binary_cols.columns,
                    summary)
coef_numerical = coef_dataframe(
                    coef_dense[np.array(nonbinary_col_selector)],
                    nonbinary_cols.columns,
                    summary)
coef_sparse = coef_dataframe(
                    clf2.coef_[0][selector_sparse],
                    sparseheaders)
                    
