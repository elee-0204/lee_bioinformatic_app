library(ggplot2)
# Basic violin plot
fileinfo <- commandArgs(trailingOnly = TRUE)
myfile <- fileinfo[1]
filepath <- fileinfo[2]

my_data <- read.delim(myfile)
#print(my_data$Read_Location )
my_data$Read_Location <- as.factor(my_data$Read_Location)
my_data$Read_Location <- factor(my_data$Read_Location,levels = c("Test1","Test2"))
my_data$Charge <- as.numeric(my_data$Charge)

pdf(filepath)
p <- ggplot(my_data, aes(x=Read_Location, y=Charge
)) + 
  geom_violin(aes(fill = Read_Location), trim = FALSE)+ 
  geom_boxplot(width = 0.13)+
  scale_fill_manual(values = c("#A1DBE0", "#F3BE4F", "#C94635","#BBBBBB"))+
  theme(legend.position = "none")+
  theme(axis.line.x = element_line(color="black", size = 0.5),
      axis.line.y = element_line(color="black", size = 0.5))

# Rotate the violin plot
p + coord_flip()
print(p)
dev.off()