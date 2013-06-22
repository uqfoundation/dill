if __name__ == '__main__':
  import sys
  import dill
  print dill.load(open(sys.argv[1],'r'))

