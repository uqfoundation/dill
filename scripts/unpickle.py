if __name__ == '__main__':
  import sys
  import dill
  for file in sys.argv[1:]:
    print (dill.load(open(file,'r')))

