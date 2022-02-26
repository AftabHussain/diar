# $Id: MyDD.py,v 1.1 2001/11/05 19:53:33 zeller Exp $
# There are two parameterized sections in this code 
# depending on the target you are delta-debugging
# The sections are denoted by the heading MODIFY_HERE #

import DD
import string
import commands
import sys
import glob
import os

import time
import timeout_decorator

###### MODIFY_HERE PART 1/2 ###
GCOV_TIMEOUT=1  
TARGET_COMMAND="./.libs/xmllint"
OUTPUT_REDIRECT="-o /dev/null"
SRC_FOLDER="./"
LD_LIBRARY_PATH="./.libs/"
SIMILARITY_THRESHOLD = 75.0
REDUCTION_THRESHOLD = 40.0
REDUCTION_TIMEOUT = 3600
###############################

max_similarity = -1.0
max_similarity_test_case_id = -1
orig_cov_exec_only = None
input_id = 0
orig_ip_len = -1

def clear_tmp_input_files():
    print("Clearing intermediate files")
    commands.getstatusoutput("rm " + inputdir + "/input.test*")

def clear_gcov_files():
    print("Clearing .gcov and .gcda files")
    commands.getstatusoutput("for i in $(find " + SRC_FOLDER + " -name '*.gcda' -o -name '*.gcov'); do rm $i; done")

# Similarity as a percentage of total covered statements of original test case
def cov_similarity_covered_statements_of_tc_main(tc_main_cov, tc_cur_cov):
    total_covered_tc_main = 0
    total_covered_tc_main_and_tc_cur = 0

    for i in range(len(tc_main_cov)):
        if tc_main_cov[i] == 1:
            total_covered_tc_main += 1
            if tc_cur_cov[i] == 1:
                total_covered_tc_main_and_tc_cur += 1

    print "total_covered_tc_main_and_tc_cur = " + str(total_covered_tc_main_and_tc_cur) + "\n"
    print "total_covered_tc_main = " + str(total_covered_tc_main) + "\n"

    return ( float(total_covered_tc_main_and_tc_cur) / total_covered_tc_main  ) * 100

# compute_cov fn objectives:
# 1. run the input testcase on the test subject (using a timeout).
# 2. compute the coverage information (discarding coverage counts).
def compute_cov(input):
        print("Computing coverage of "+input.name)
        print("(Original test: " + inputfilename + ")")

        (status, output) = commands.getstatusoutput("LD_LIBRARY_PATH=\"" + LD_LIBRARY_PATH + "\" timeout " + str(GCOV_TIMEOUT) + " " + TARGET_COMMAND + " " + input.name + " " + OUTPUT_REDIRECT)

        print(input.name)       

        commands.getstatusoutput("for i in $(find " + SRC_FOLDER + " -name '*.gcno'); do gcov $i; done")
        commands.getstatusoutput("for i in $(find " + SRC_FOLDER + " -name '*.gcov'); do cat $i >> final.gcov; done")
       
        with open('final.gcov', 'r') as file:
           cov = file.read()

        # Remove leading and trailing white spaces from whole string
        cov = cov.strip()

        ## CREATING COVERAGE INFO WITHOUT COUNT OF NO. OF TIMES EACH STATEMENT IS EXECUTED

        # Get a list of all statements
        # -------------------------------------------------------------------
	# IMP Note: (Since we compare "cov_list"s obtained for different test
	# cases to compare their coverages, which we turn into a 0/1 sequence
	# of numbers, the important assumption here is that cov_list gives us
	# the same list of statements for all the inputs, and that the list of
	# statements are in the same order -- this assumption further subsumes
	# that gcov is behaving in the same way interms of returning the same
	# statements for both the tests, in the same order. Also, in the
	# concatenation process above using cat, we concatenate all the data
	# into final.gcov in the same order, i.e.  "find" yields the same list
	# of gcov files, in exactly the same order -- which it should), 
        cov_list = cov.split("\n")

        # Remove leading and trailing white spaces from each statement
        cov_list = [statement.strip() for statement in cov_list]

        # Replace no. of execution counts: 
        for i in range(len(cov_list)):

          # Extract the first term of the gcov line 
          exec_info = cov_list[i][:cov_list[i].index(":")] 
          if(exec_info!="-" and exec_info!="#####"):
            cov_list[i] = 1 #"X" + cur_cov_list[i][cur_cov_list[i].index(":"):]
            continue;
          else:
            cov_list[i] = 0
            continue;

          # Remove No. of Runs entry
          if cov_list[i].find(":Runs:") != -1:
            cov_list[i] = 0

        cov_exec_only = []
        for statement in cov_list:
          cov_exec_only.append(statement)

        return cov_exec_only, status

class MyDD(DD.DD):

    # Override the coerce API
    def coerce(self, deltas):
        input = ""
        for (index, ch) in deltas:
          input = input + ch
        return input

    def __init__(self):
        DD.DD.__init__(self)
        
    def _test(self, deltas):
        global max_similarity, max_similarity_test_case_id, orig_ip_len 
	# Clear the .gcov, *.gcda files (*.gcno is produced once during compilation)
        #commands.getstatusoutput("rm *.gcov *.gcda")
        clear_gcov_files()

        # Build input
        input = ""
        for (index, ch) in deltas:
          input = input + ch

        global orig_cov, orig_cov_exec_only, input_id
        input_id+=1

        # Write input to `input.test'
        input_file = open(inputdir+"/input.test"+str(input_id), 'w+')
        input_file.write(input)
        
	input_file.flush();
        
        # Invoke test subject and get coverage information
        cur_cov_exec_only, exit_status = compute_cov(input_file)
        new_ip_len = os.path.getsize(input_file.name)

        input_file.close()


        if len(input)==0:
           print "This test case is empty"
           return self.PASS

        similarity = cov_similarity_covered_statements_of_tc_main(orig_cov_exec_only, cur_cov_exec_only)
        reduction_ratio = (float((orig_ip_len - new_ip_len)/float(orig_ip_len)))*100
        #commands.getstatusoutput("echo " + str(reduction_ratio) + "," + str(similarity) + ">> rr_sim.csv")
        if input_id == 2:
            return self.FAIL #assume the original test case satisfies the criteria
        if similarity >= float(SIMILARITY_THRESHOLD) and reduction_ratio >= float(REDUCTION_THRESHOLD) and exit_status == 0:
           print "This test case SATISFIES the condition"
           print "similarity:"
           print similarity
           print "reduction_ratio:"
           print reduction_ratio
           print "exit_status:"
           print exit_status
           print "This test case has >= " + str(SIMILARITY_THRESHOLD) + "% coverage similarity with coverage of the original test case"
           print "This test is >= " + str(REDUCTION_THRESHOLD) + "% smaller than the original test case"
           if similarity >= max_similarity and input_id!=2: #ignore the match with the original test case
               max_similarity = similarity
               max_similarity_test_case_id = input_id
           return self.FAIL
        else:
           print "This test case does not satisfy the condition"
           print "similarity:"
           print similarity
           print "reduction_ratio:"
           print reduction_ratio
           print "exit_status:"
           print exit_status
           if similarity > max_similarity and input_id!=2: #ignore the match with the original test case
               max_similarity = similarity
               max_similarity_test_case_id = input_id
           return self.PASS

def clear():
     # Clear all temporary files
     clear_tmp_input_files()
     # Clear the .gcov, *.gcda files (*.gcno is produced once during compilation)
     clear_gcov_files()

@timeout_decorator.timeout(REDUCTION_TIMEOUT, timeout_exception=StopIteration)
def timed_reduce():
  print("Start")
  mydd = MyDD()
  
  c = mydd.ddmin(deltas)              # Invoke DDMIN

  output_file = open(outputfilename, 'w')
  output_file.write(mydd.coerce(c))
  
  output_file.close()
  
  clear()
  commands.getstatusoutput("echo \""+outputfilename+","+ str(max_similarity) + "," + str(os.path.getsize(outputfilename)) + "\" >> reduced_tests" )
  print("all done!")

def untimed_reduce():
  print("Start")
  mydd = MyDD()
  
  c = mydd.ddmin(deltas)              # Invoke DDMIN

  output_file = open(outputfilename, 'w')
  output_file.write(mydd.coerce(c))
  
  output_file.close()
  
  clear()
  commands.getstatusoutput("echo \""+outputfilename+","+ str(max_similarity) + "," + str(os.path.getsize(outputfilename)) + "\" >> reduced_tests" )
  print("all done!")

if __name__ == '__main__':

    inputfilename=sys.argv[1]
    outputfilename=sys.argv[2]
    inputdir=sys.argv[3]

    clear()

    # Run and Compute coverage from input testcase
    input_file = open(inputfilename, 'r')
    #input_file.flush()
    orig_cov_exec_only, exit_status = compute_cov(input_file)
    orig_ip_len = os.path.getsize(inputfilename)

    # Load deltas from input testcase
    deltas = []
    index = 1

############# MODIFY_HERE PART 2/2 ###########

    # Using character deltas
    for chunk in input_file.read():
       deltas.append((index, chunk))
       index += 1

    '''
    # Using byte deltas
    FIRST_CHUNK_SIZE=128
    REST_CHUNK_SIZE=8
    chunk = input_file.read(FIRST_CHUNK_SIZE)
    while chunk:
      deltas.append((index, chunk))
      index += 1
      chunk = input_file.read(REST_CHUNK_SIZE)
    '''

##############################################

    input_file.close()

    untimed_reduce()

